import uuid
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import dependencies
from app.core.exceptions import (
    DocumentStorageUnavailableError,
    IngestionQueueUnavailableError,
    UnsupportedDocumentError,
)
from app.models.document import Document, DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.documents import DocumentService
from app.services.knowledge_base import KnowledgeBaseNotFoundError


class FakeKnowledgeBaseRepository:
    def __init__(self, item: KnowledgeBase | None) -> None:
        self.item = item

    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None:
        if self.item is not None and self.item.id == item_id:
            return self.item
        return None


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Document] = {}

    async def add(self, document: Document) -> None:
        self.items[document.id] = document

    async def get(
        self, document_id: uuid.UUID, knowledge_base_id: uuid.UUID | None = None
    ) -> Document | None:
        document = self.items.get(document_id)
        if document is not None and (
            knowledge_base_id is None or document.knowledge_base_id == knowledge_base_id
        ):
            return document
        return None


class FakeTaskRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, IngestionTask] = {}

    async def add(self, task: IngestionTask) -> None:
        self.items[task.id] = task

    async def get(self, task_id: uuid.UUID) -> IngestionTask | None:
        return self.items.get(task_id)


def make_service(
    *,
    session: AsyncSession | None = None,
    storage: AsyncMock | None = None,
    queue: AsyncMock | None = None,
    knowledge_base: KnowledgeBase | None = None,
) -> tuple[
    DocumentService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    uuid.UUID,
    FakeDocumentRepository,
    FakeTaskRepository,
]:
    actual_session = cast(AsyncMock, session) if session is not None else AsyncMock()
    actual_storage = storage or AsyncMock()
    actual_queue = queue or AsyncMock()
    actual_queue.enqueue.return_value = "arq-job-1"
    kb = knowledge_base or KnowledgeBase(
        id=uuid.uuid4(),
        name="docs",
        description="",
        embedding_model="hashing",
        embedding_dimension=64,
    )
    documents = FakeDocumentRepository()
    tasks = FakeTaskRepository()
    service = DocumentService(
        knowledge_bases=FakeKnowledgeBaseRepository(kb),
        documents=documents,
        tasks=tasks,
        session=cast(AsyncSession, actual_session),
        storage=actual_storage,
        queue=actual_queue,
    )
    return service, actual_session, actual_storage, actual_queue, kb.id, documents, tasks


async def test_upload_stores_commits_enqueues_and_records_job_id() -> None:
    service, session, storage, queue, knowledge_base_id, _, _ = make_service()

    document, task = await service.upload(
        knowledge_base_id, "folder/readme.md", "text/markdown", b"# hello"
    )

    storage.put.assert_awaited_once_with(document.source_object_key, b"# hello", "text/markdown")
    queue.enqueue.assert_awaited_once_with(task.id, document.id)
    assert task.arq_job_id == "arq-job-1"
    assert session.commit.await_count == 2


async def test_database_failure_rolls_back_and_deletes_uploaded_object() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.commit.side_effect = RuntimeError("database unavailable")
    service, _, storage, queue, knowledge_base_id, _, _ = make_service(session=session)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.upload(knowledge_base_id, "readme.md", "text/markdown", b"content")

    session.rollback.assert_awaited_once()
    storage.delete.assert_awaited_once()
    queue.enqueue.assert_not_awaited()


async def test_cleanup_failure_preserves_original_database_error() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.commit.side_effect = RuntimeError("database unavailable")
    storage = AsyncMock()
    storage.delete.side_effect = RuntimeError("cleanup unavailable")
    service, _, _, _, knowledge_base_id, _, _ = make_service(session=session, storage=storage)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.upload(knowledge_base_id, "readme.md", "text/markdown", b"content")


async def test_queue_failure_marks_records_failed_and_preserves_source() -> None:
    queue = AsyncMock()
    queue.enqueue.side_effect = RuntimeError("redis unavailable")
    service, session, storage, _, knowledge_base_id, documents, tasks = make_service(queue=queue)

    with pytest.raises(IngestionQueueUnavailableError) as error:
        await service.upload(knowledge_base_id, "readme.md", "text/markdown", b"content")

    document = next(iter(documents.items.values()))
    task = next(iter(tasks.items.values()))
    assert error.value.__cause__ is not None
    assert document.status == DocumentStatus.FAILED
    assert task.status == TaskStatus.FAILED
    assert document.error == "redis unavailable"
    assert task.error == "redis unavailable"
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 2
    storage.delete.assert_not_awaited()


async def test_storage_failure_is_mapped_and_database_is_untouched() -> None:
    storage = AsyncMock()
    storage.put.side_effect = RuntimeError("minio unavailable")
    service, session, _, queue, knowledge_base_id, _, _ = make_service(storage=storage)

    with pytest.raises(DocumentStorageUnavailableError) as error:
        await service.upload(knowledge_base_id, "readme.md", "text/markdown", b"content")

    assert isinstance(error.value.__cause__, RuntimeError)
    session.commit.assert_not_awaited()
    queue.enqueue.assert_not_awaited()


async def test_missing_knowledge_base_does_not_store_file() -> None:
    service, session, storage, _, _, _, _ = make_service()

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.upload(uuid.uuid4(), "readme.md", "text/markdown", b"content")

    storage.put.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_invalid_file_does_not_store_file() -> None:
    service, session, storage, _, knowledge_base_id, _, _ = make_service()

    with pytest.raises(UnsupportedDocumentError):
        await service.upload(knowledge_base_id, "payload.exe", "application/octet-stream", b"x")

    storage.put.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_document_queue_defers_pool_creation_until_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AsyncMock()
    pool.enqueue_job.return_value = type("Job", (), {"job_id": "job-1"})()
    create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr(dependencies, "create_pool", create_pool)

    queue = dependencies.get_document_ingestion_queue()

    create_pool.assert_not_awaited()
    assert await queue.enqueue(uuid.uuid4(), uuid.uuid4()) == "job-1"
    create_pool.assert_awaited_once()
    pool.aclose.assert_awaited_once()
