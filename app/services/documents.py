import logging
import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentCleanupFailedError,
    DocumentStorageUnavailableError,
    IngestionQueueUnavailableError,
)
from app.infrastructure.object_storage import ObjectStorage, source_key
from app.infrastructure.queue import IngestionQueue
from app.models.document import Document, DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.documents import validate_upload
from app.services.knowledge_base import KnowledgeBaseNotFoundError

logger = logging.getLogger(__name__)


class KnowledgeBaseRepositoryProtocol(Protocol):
    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None: ...


class DocumentRepositoryProtocol(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(
        self,
        document_id: uuid.UUID,
        knowledge_base_id: uuid.UUID | None = None,
    ) -> Document | None: ...


class IngestionTaskRepositoryProtocol(Protocol):
    async def add(self, task: IngestionTask) -> None: ...

    async def get(self, task_id: uuid.UUID) -> IngestionTask | None: ...


class DocumentService:
    def __init__(
        self,
        knowledge_bases: KnowledgeBaseRepositoryProtocol,
        documents: DocumentRepositoryProtocol,
        tasks: IngestionTaskRepositoryProtocol,
        session: AsyncSession,
        storage: ObjectStorage,
        queue: IngestionQueue,
    ) -> None:
        self.knowledge_bases = knowledge_bases
        self.documents = documents
        self.tasks = tasks
        self._session = session
        self._storage = storage
        self._queue = queue

    async def upload(
        self,
        knowledge_base_id: uuid.UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> tuple[Document, IngestionTask]:
        if await self.knowledge_bases.get_by_id(knowledge_base_id) is None:
            raise KnowledgeBaseNotFoundError

        safe_filename = validate_upload(filename, content)
        document = Document(
            id=uuid.uuid4(),
            knowledge_base_id=knowledge_base_id,
            filename=safe_filename,
            content_type=content_type,
            size_bytes=len(content),
            source_object_key="",
            status=DocumentStatus.PENDING,
        )
        document.source_object_key = source_key(knowledge_base_id, document.id, safe_filename)
        task = IngestionTask(
            id=uuid.uuid4(),
            document_id=document.id,
            status=TaskStatus.PENDING,
        )

        try:
            await self._storage.put(document.source_object_key, content, content_type)
        except Exception as exc:
            raise DocumentStorageUnavailableError("Document storage is unavailable") from exc

        try:
            await self.documents.add(document)
            await self.tasks.add(task)
            await self._session.commit()
        except Exception:
            try:
                await self._session.rollback()
            except Exception:
                logger.exception(
                    "Failed to roll back document records after database failure",
                    extra={"source_object_key": document.source_object_key},
                )
            try:
                await self._storage.delete(document.source_object_key)
            except Exception:
                logger.exception(
                    "Failed to delete uploaded object after database failure",
                    extra={"source_object_key": document.source_object_key},
                )
            raise

        document_id = document.id
        task_id = task.id
        try:
            job_id = await self._queue.enqueue(task_id, document_id)
        except Exception as exc:
            try:
                await self._session.rollback()
            except Exception:
                logger.exception(
                    "Failed to roll back before marking enqueue failure",
                    extra={"document_id": document_id, "task_id": task_id},
                )
            try:
                await self._mark_enqueue_failed(document_id, task_id, str(exc))
            except Exception as compensation_error:
                logger.exception(
                    "Failed to persist enqueue failure compensation",
                    exc_info=compensation_error,
                    extra={"document_id": document_id, "task_id": task_id},
                )
                raise DocumentCleanupFailedError(
                    "Failed to persist ingestion queue compensation"
                ) from exc
            raise IngestionQueueUnavailableError("Ingestion queue is unavailable") from exc

        task.arq_job_id = job_id
        try:
            await self._session.commit()
        except Exception as commit_error:
            try:
                await self._session.rollback()
            except Exception:
                logger.exception(
                    "Failed to roll back job ID commit",
                    extra={"document_id": document_id, "task_id": task_id},
                )
            try:
                return await self._recover_enqueued_task(document_id, task_id, job_id)
            except Exception as compensation_error:
                logger.exception(
                    "Failed to recover an enqueued task after job ID commit failure",
                    exc_info=compensation_error,
                    extra={"document_id": document_id, "task_id": task_id},
                )
                raise DocumentCleanupFailedError(
                    "Failed to persist the enqueued task job ID"
                ) from commit_error

        return document, task

    async def _recover_enqueued_task(
        self,
        document_id: uuid.UUID,
        task_id: uuid.UUID,
        job_id: str,
    ) -> tuple[Document, IngestionTask]:
        document = await self.documents.get(document_id)
        task = await self.tasks.get(task_id)
        if document is None or task is None:
            raise RuntimeError("Committed ingestion records could not be reloaded")
        task.arq_job_id = job_id
        await self._session.commit()
        return document, task

    async def _mark_enqueue_failed(
        self,
        document_id: uuid.UUID,
        task_id: uuid.UUID,
        error: str,
    ) -> None:
        document = await self.documents.get(document_id)
        task = await self.tasks.get(task_id)
        if document is None or task is None:
            raise RuntimeError("Committed ingestion records could not be reloaded")
        document.status = DocumentStatus.FAILED
        document.error = error
        task.status = TaskStatus.FAILED
        task.error = error
        await self._session.commit()
