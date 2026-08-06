from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.document import Document, DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStage, TaskStatus
from app.rag.chunking import chunk_text
from app.rag.embedding import HashingEmbedder
from app.rag.types import IndexedChunk
from app.repositories.ingestion_tasks import IngestionTaskRepository


class IngestionService:
    def __init__(
        self, session_factory: Any, storage: Any, index: Any, embedder: Any | None = None
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.index = index
        self.embedder = embedder or HashingEmbedder()

    async def run(self, task_id: str | uuid.UUID, document_id: str | uuid.UUID) -> None:
        tid, did = uuid.UUID(str(task_id)), uuid.UUID(str(document_id))
        async with self.session_factory() as session:
            task = await IngestionTaskRepository(session).get(tid)
            if task is None or task.document_id != did or task.status == TaskStatus.COMPLETED:
                return
            claimed = await IngestionTaskRepository(session).claim_pending(tid)
            if claimed is None:
                if task.status == TaskStatus.COMPLETED:
                    return
                return
            await session.commit()
        try:
            async with self.session_factory() as session:
                task = await session.get(IngestionTask, tid)
                document = await session.get(Document, did)
                if task is None or document is None:
                    raise ValueError("ingestion task or document not found")
                document.status = DocumentStatus.PROCESSING
                task.stage, task.progress = TaskStage.PARSING, 20
                await session.commit()
            source = (await self.storage.get(document.source_object_key)).decode("utf-8")
            parsed_key = (
                document.parsed_object_key
                or f"{document.source_object_key.rsplit('/source/', 1)[0]}/parsed.json"
            )
            await self.storage.put(
                parsed_key,
                json.dumps({"text": source}, ensure_ascii=False).encode(),
                "application/json",
            )
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                task = await session.get(IngestionTask, tid)
                document.parsed_object_key = parsed_key
                task.stage, task.progress = TaskStage.CHUNKING, 40
                await session.commit()
            chunks = chunk_text(source)
            async with self.session_factory() as session:
                task = await session.get(IngestionTask, tid)
                task.stage, task.progress = TaskStage.EMBEDDING, 60
                await session.commit()
            indexed = [
                IndexedChunk(
                    document.knowledge_base_id,
                    did,
                    document.filename,
                    str(c.index),
                    c.text,
                    c.start,
                    c.end,
                    self.embedder.embed(c.text),
                )
                for c in chunks
            ]
            async with self.session_factory() as session:
                task = await session.get(IngestionTask, tid)
                task.stage, task.progress = TaskStage.INDEXING, 80
                await session.commit()
            await self.index.replace_document(document.knowledge_base_id, did, indexed)
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                task = await session.get(IngestionTask, tid)
                document.status, document.chunk_count = DocumentStatus.COMPLETED, len(indexed)
                task.status, task.stage, task.progress, task.completed_at = (
                    TaskStatus.COMPLETED,
                    TaskStage.COMPLETED,
                    100,
                    datetime.now(UTC),
                )
                await session.commit()
        except Exception as exc:
            async with self.session_factory() as session:
                task = await session.get(IngestionTask, tid)
                document = await session.get(Document, did)
                if task:
                    task.status, task.error = TaskStatus.FAILED, str(exc)
                if document:
                    document.status, document.error = DocumentStatus.FAILED, str(exc)
                await session.commit()
            raise
