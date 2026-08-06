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
    def __init__(self, session_factory: Any, storage: Any, index: Any, embedder: Any | None = None) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.index = index
        self.embedder = embedder or HashingEmbedder()

    async def _progress(self, tid: uuid.UUID, did: uuid.UUID, stage: TaskStage, progress: int, *, document_status: str | None = None) -> None:
        async with self.session_factory() as session:
            task = await session.get(IngestionTask, tid)
            document = await session.get(Document, did)
            if task is None:
                return
            task.stage, task.progress = stage, progress
            if document is not None and document_status is not None:
                document.status = document_status
            await session.commit()

    async def _mark_failed(self, tid: uuid.UUID, did: uuid.UUID, error: str) -> None:
        try:
            async with self.session_factory() as session:
                try:
                    task = await session.get(IngestionTask, tid)
                    document = await session.get(Document, did)
                    if task is not None:
                        task.status, task.error = TaskStatus.FAILED, error
                    if document is not None:
                        document.status, document.error = DocumentStatus.FAILED, error
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            # Compensation must never replace the original processing error.
            pass

    async def run(self, task_id: str | uuid.UUID, document_id: str | uuid.UUID) -> None:
        tid, did = uuid.UUID(str(task_id)), uuid.UUID(str(document_id))
        async with self.session_factory() as session:
            task = await IngestionTaskRepository(session).get(tid)
            if task is None or task.document_id != did or task.status == TaskStatus.COMPLETED:
                return
            claimed = await IngestionTaskRepository(session).claim_pending(tid)
            if claimed is None:
                return
            await session.commit()
        try:
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                if document is None or await session.get(IngestionTask, tid) is None:
                    raise ValueError("ingestion task or document not found")
                source_key = document.source_object_key
                parsed_key = document.parsed_object_key or f"{source_key.rsplit('/source/', 1)[0]}/parsed.json"
            await self._progress(tid, did, TaskStage.PARSING, 20, document_status=DocumentStatus.PROCESSING)
            source = (await self.storage.get(source_key)).decode("utf-8")
            await self.storage.put(parsed_key, json.dumps({"text": source}, ensure_ascii=False).encode(), "application/json")
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                if document is not None:
                    document.parsed_object_key = parsed_key
                await session.commit()
            await self._progress(tid, did, TaskStage.CHUNKING, 40)
            chunks = chunk_text(source)
            await self._progress(tid, did, TaskStage.EMBEDDING, 60)
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                if document is None:
                    raise ValueError("document not found")
                kb_id, filename = document.knowledge_base_id, document.filename
            indexed = [IndexedChunk(kb_id, did, filename, str(c.index), c.text, c.start, c.end, self.embedder.embed(c.text)) for c in chunks]
            await self._progress(tid, did, TaskStage.INDEXING, 80)
            await self.index.replace_document(kb_id, did, indexed)
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                task = await session.get(IngestionTask, tid)
                if document is not None:
                    document.status, document.chunk_count = DocumentStatus.COMPLETED, len(indexed)
                if task is not None:
                    task.status, task.stage, task.progress, task.completed_at = TaskStatus.COMPLETED, TaskStage.COMPLETED, 100, datetime.now(UTC)
                await session.commit()
        except Exception as exc:
            await self._mark_failed(tid, did, str(exc))
            raise
