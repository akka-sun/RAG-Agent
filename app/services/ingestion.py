from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.exceptions import DocumentCleanupFailedError
from app.models.document import Document, DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStage, TaskStatus
from app.observability import get_langfuse_tracer, get_trace_context, set_trace_context
from app.parsers.router import ParserRouter
from app.parsers.types import ParsedDocument
from app.rag.chunking import chunk_parsed_document
from app.rag.embedding import HashingEmbedder
from app.rag.types import IndexedChunk
from app.repositories.ingestion_tasks import IngestionTaskRepository

logger = logging.getLogger(__name__)


class ParserRouterProtocol(Protocol):
    async def parse_document(
        self,
        filename: str,
        content: bytes,
        parser: str | None,
    ) -> ParsedDocument: ...


class IngestionService:
    def __init__(
        self,
        session_factory: Any,
        storage: Any,
        index: Any,
        embedder: Any | None = None,
        parser_router: ParserRouterProtocol | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.index = index
        self.embedder = embedder or HashingEmbedder()
        self.parser_router = parser_router or ParserRouter()

    async def _progress(
        self,
        tid: uuid.UUID,
        did: uuid.UUID,
        stage: TaskStage,
        progress: int,
        *,
        document_status: str | None = None,
    ) -> None:
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

    async def run(self, task_id: str | uuid.UUID, document_id: str | uuid.UUID) -> None:
        tid, did = uuid.UUID(str(task_id)), uuid.UUID(str(document_id))
        parsed_key: str | None = None
        parsed_written = False
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
                filename = document.filename
                parser_name = getattr(document, "parser_name", "local")
                parsed_key = document.parsed_object_key or (
                    f"{source_key.rsplit('/source/', 1)[0]}/parsed.json"
                )
            set_trace_context(
                stage="parse",
                document_id=str(did),
                task_id=str(tid),
                parser=parser_name,
            )
            logger.info("ingestion parsing started")
            await self._progress(
                tid,
                did,
                TaskStage.PARSING,
                20,
                document_status=DocumentStatus.PROCESSING,
            )
            with get_langfuse_tracer().span("ingestion.parse", get_trace_context().as_dict()):
                source = await self.storage.get(source_key)
                parsed_document = await self.parser_router.parse_document(
                    filename, source, parser_name
                )
            parsed = parsed_document.model_dump_json().encode("utf-8")
            await self.storage.put(parsed_key, parsed, "application/json")
            parsed_written = True
            set_trace_context(stage="chunk", document_id=str(did), task_id=str(tid))
            logger.info("ingestion chunking started")
            await self._progress(tid, did, TaskStage.CHUNKING, 40)
            with get_langfuse_tracer().span("ingestion.chunk", get_trace_context().as_dict()):
                chunks = chunk_parsed_document(parsed_document)
            set_trace_context(stage="embed", document_id=str(did), task_id=str(tid))
            logger.info("ingestion embedding started")
            await self._progress(tid, did, TaskStage.EMBEDDING, 60)
            with get_langfuse_tracer().span("ingestion.embed", get_trace_context().as_dict()):
                vectors = await self._embed_texts([chunk.text for chunk in chunks])
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                if document is None:
                    raise ValueError("document not found")
                kb_id, filename = document.knowledge_base_id, document.filename
            indexed = [
                IndexedChunk(
                    kb_id,
                    did,
                    filename,
                    str(chunk.index),
                    chunk.text,
                    chunk.start,
                    chunk.end,
                    vectors[index],
                    page_number=_metadata_int(chunk.metadata, "page_number"),
                    section=_metadata_str(chunk.metadata, "section"),
                    parser_name=_metadata_str(chunk.metadata, "parser"),
                    block_index=_metadata_int(chunk.metadata, "block_index"),
                    metadata=chunk.metadata,
                )
                for index, chunk in enumerate(chunks)
            ]
            set_trace_context(
                stage="index", document_id=str(did), task_id=str(tid), knowledge_base_id=str(kb_id)
            )
            logger.info("ingestion indexing started")
            await self._progress(tid, did, TaskStage.INDEXING, 80)
            with get_langfuse_tracer().span("ingestion.index", get_trace_context().as_dict()):
                await self.index.replace_document(kb_id, did, indexed)
            async with self.session_factory() as session:
                document = await session.get(Document, did)
                task = await session.get(IngestionTask, tid)
                if document is not None:
                    document.status = DocumentStatus.COMPLETED
                    document.parsed_object_key = parsed_key
                    document.chunk_count = len(indexed)
                if task is not None:
                    task.status = TaskStatus.COMPLETED
                    task.stage = TaskStage.COMPLETED
                    task.progress = 100
                    task.completed_at = datetime.now(UTC)
                await session.commit()
        except Exception as exc:
            compensation_failures: list[str] = []
            try:
                await self._mark_failed(tid, did, str(exc))
            except Exception as mark_error:
                compensation_failures.append(f"failed status: {mark_error}")
            if parsed_written and parsed_key is not None:
                try:
                    await self.storage.delete(parsed_key)
                except Exception as delete_error:
                    compensation_failures.append(f"parsed object: {delete_error}")
            if compensation_failures:
                details = "; ".join(compensation_failures)
                raise DocumentCleanupFailedError(f"Ingestion cleanup failed ({details})") from exc
            raise

    async def _embed_texts(self, texts: list[str]) -> list[tuple[float, ...]]:
        embed_texts = getattr(self.embedder, "embed_texts", None)
        if embed_texts is not None:
            raw_vectors = await embed_texts(texts)
        else:
            raw_vectors = [self.embedder.embed(text) for text in texts]
        if len(raw_vectors) != len(texts):
            msg = "embedding client returned a different number of vectors"
            raise ValueError(msg)
        return [tuple(float(value) for value in vector) for vector in raw_vectors]


def _metadata_int(metadata: Mapping[str, object], key: str) -> int | None:
    value = metadata.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _metadata_str(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value:
        return value
    return None
