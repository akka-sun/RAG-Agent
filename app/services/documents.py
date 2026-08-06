import logging
import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
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
        )
        document.source_object_key = source_key(knowledge_base_id, document.id, safe_filename)
        task = IngestionTask(id=uuid.uuid4(), document_id=document.id)

        try:
            await self._storage.put(document.source_object_key, content, content_type)
        except Exception as exc:
            raise DocumentStorageUnavailableError("Document storage is unavailable") from exc

        try:
            await self.documents.add(document)
            await self.tasks.add(task)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
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
            task.arq_job_id = await self._queue.enqueue(task_id, document_id)
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            await self._mark_enqueue_failed(document_id, task_id, str(exc))
            raise IngestionQueueUnavailableError("Ingestion queue is unavailable") from exc

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
