import logging
import uuid
from typing import Any, Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentCleanupFailedError,
    DocumentNotFoundError,
    DocumentNotRetryableError,
    DocumentStorageUnavailableError,
    IngestionQueueUnavailableError,
    IngestionTaskNotFoundError,
    ParsedDocumentNotReadyError,
)
from app.infrastructure.object_storage import ObjectStorage, source_key
from app.infrastructure.queue import IngestionQueue
from app.models.document import Document, DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.documents import normalize_content_type, validate_upload
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

    async def list_by_knowledge_base(self, knowledge_base_id: uuid.UUID) -> list[Document]: ...

    async def delete(self, document: Document) -> None: ...


class IngestionTaskRepositoryProtocol(Protocol):
    async def add(self, task: IngestionTask) -> None: ...

    async def get(self, task_id: uuid.UUID) -> IngestionTask | None: ...

    async def has_active_task(self, document_id: uuid.UUID) -> bool: ...

    async def delete_by_document(self, document_id: uuid.UUID) -> None: ...


class DocumentIndexProtocol(Protocol):
    async def delete_document(
        self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID
    ) -> None: ...


class NullDocumentIndex:
    async def delete_document(self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID) -> None:
        del knowledge_base_id, document_id


class DocumentService:
    def __init__(
        self,
        knowledge_bases: KnowledgeBaseRepositoryProtocol,
        documents: Any,
        tasks: Any,
        session: AsyncSession,
        storage: ObjectStorage,
        queue: IngestionQueue,
        index: DocumentIndexProtocol | None = None,
    ) -> None:
        self.knowledge_bases = knowledge_bases
        self.documents = documents
        self.tasks = tasks
        self._session = session
        self._storage = storage
        self._queue = queue
        self._index = index or NullDocumentIndex()

    async def list_documents(self, knowledge_base_id: uuid.UUID) -> list[Document]:
        if await self.knowledge_bases.get_by_id(knowledge_base_id) is None:
            raise KnowledgeBaseNotFoundError
        return await self.documents.list_by_knowledge_base(knowledge_base_id)

    async def get_document(self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID) -> Document:
        document = await self.documents.get(document_id, knowledge_base_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        return document

    async def get_task(self, task_id: uuid.UUID) -> IngestionTask:
        task = await self.tasks.get(task_id)
        if task is None:
            raise IngestionTaskNotFoundError("Ingestion task not found")
        return task

    async def download_source(
        self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID
    ) -> tuple[str, str, bytes]:
        document = await self.get_document(knowledge_base_id, document_id)
        try:
            content = await self._storage.get(document.source_object_key)
        except Exception as exc:
            raise DocumentStorageUnavailableError("Document storage is unavailable") from exc
        return document.filename, document.content_type, content

    async def download_parsed(self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID) -> bytes:
        document = await self.get_document(knowledge_base_id, document_id)
        if document.parsed_object_key is None:
            raise ParsedDocumentNotReadyError("Parsed document is not ready")
        try:
            return await self._storage.get(document.parsed_object_key)
        except Exception as exc:
            raise DocumentStorageUnavailableError("Document storage is unavailable") from exc

    async def retry(self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID) -> IngestionTask:
        document = await self.documents.get_for_update(document_id, knowledge_base_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        if document.status != DocumentStatus.FAILED or await self.tasks.has_active_task(
            document.id
        ):
            raise DocumentNotRetryableError("Only failed documents without active tasks can retry")
        try:
            await self._index.delete_document(knowledge_base_id, document_id)
        except Exception as exc:
            await self._session.rollback()
            raise DocumentCleanupFailedError("Document cleanup failed") from exc
        task = IngestionTask(id=uuid.uuid4(), document_id=document.id, status=TaskStatus.PENDING)
        document.status = DocumentStatus.PENDING
        document.error = None
        try:
            await self.tasks.add(task)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DocumentNotRetryableError(
                "Only one active ingestion task is allowed per document"
            ) from exc
        try:
            job_id = await self._queue.enqueue(task.id, document.id)
            task.arq_job_id = job_id
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            if task.arq_job_id is not None:
                try:
                    _, recovered_task = await self._recover_enqueued_task(
                        document.id, task.id, task.arq_job_id
                    )
                    return recovered_task
                except Exception as compensation_error:
                    raise DocumentCleanupFailedError(
                        "Failed to persist the enqueued task job ID"
                    ) from compensation_error
            await self._mark_enqueue_failed(document.id, task.id, str(exc))
            raise IngestionQueueUnavailableError("Ingestion queue is unavailable") from exc
        return task

    async def delete(self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID) -> None:
        document = await self.documents.get_for_update(document_id, knowledge_base_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        active_status = document.status in (
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
        )
        if active_status or await self.tasks.has_active_task(document.id):
            raise DocumentNotRetryableError("Active documents cannot be deleted")
        try:
            await self._index.delete_document(knowledge_base_id, document_id)
            if document.parsed_object_key is not None:
                await self._storage.delete(document.parsed_object_key)
            await self._storage.delete(document.source_object_key)
        except Exception as exc:
            await self._session.rollback()
            raise DocumentCleanupFailedError("Document cleanup failed") from exc
        await self.tasks.delete_by_document(document.id)
        await self.documents.delete(document)
        await self._session.commit()

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
        safe_content_type = normalize_content_type(content_type)
        document = Document(
            id=uuid.uuid4(),
            knowledge_base_id=knowledge_base_id,
            filename=safe_filename,
            content_type=safe_content_type,
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
            await self._storage.put(document.source_object_key, content, safe_content_type)
        except Exception as exc:
            raise DocumentStorageUnavailableError("Document storage is unavailable") from exc

        try:
            await self.documents.add(document)
            await self.tasks.add(task)
            await self._session.commit()
        except Exception as database_error:
            try:
                await self._session.rollback()
            except Exception:
                logger.exception(
                    "Failed to roll back document records after database failure",
                    extra={"source_object_key": document.source_object_key},
                )
            try:
                await self._storage.delete(document.source_object_key)
            except Exception as cleanup_error:
                logger.exception(
                    "Failed to delete uploaded object after database failure",
                    extra={"source_object_key": document.source_object_key},
                )
                raise DocumentCleanupFailedError(
                    f"Failed to delete uploaded source object: {cleanup_error}"
                ) from database_error
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
