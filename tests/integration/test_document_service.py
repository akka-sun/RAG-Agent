import asyncio
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.exceptions import (
    DocumentCleanupFailedError,
    DocumentNotRetryableError,
    IngestionQueueUnavailableError,
)
from app.models.document import Document, DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStatus
from app.models.knowledge_base import KnowledgeBase
from app.repositories.documents import DocumentRepository
from app.repositories.ingestion_tasks import IngestionTaskRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.documents import DocumentService


class MemoryStorage:
    def __init__(self, fail_delete: str | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_delete = fail_delete

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        if key == self.fail_delete:
            raise RuntimeError("storage unavailable")
        del self.objects[key]


class MemoryIndex:
    def __init__(self, fail: bool = False) -> None:
        self.documents: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.fail = fail

    async def delete_document(self, knowledge_base_id: uuid.UUID, document_id: uuid.UUID) -> None:
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.documents.discard((knowledge_base_id, document_id))


class FixedQueue:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def enqueue(self, task_id: uuid.UUID, document_id: uuid.UUID) -> str:
        del document_id
        if self.error is not None:
            raise self.error
        return str(task_id)


async def make_service(
    session: AsyncSession,
    queue: FixedQueue,
) -> tuple[DocumentService, KnowledgeBase, MemoryStorage]:
    knowledge_base = KnowledgeBase(
        name=f"service-{uuid.uuid4()}",
        description="",
        embedding_model="hashing",
        embedding_dimension=64,
    )
    session.add(knowledge_base)
    await session.commit()
    storage = MemoryStorage()
    return (
        DocumentService(
            knowledge_bases=KnowledgeBaseRepository(session),
            documents=DocumentRepository(session),
            tasks=IngestionTaskRepository(session),
            session=session,
            storage=storage,
            queue=queue,
        ),
        knowledge_base,
        storage,
    )


async def test_service_persists_fixed_job_id_with_real_postgres(
    db_session: AsyncSession,
) -> None:
    service, knowledge_base, _ = await make_service(db_session, FixedQueue())

    document, task = await service.upload(
        knowledge_base.id, "notes.md", "text/markdown", b"# notes"
    )
    document_id, task_id = document.id, task.id

    db_session.expire_all()
    stored_document = await DocumentRepository(db_session).get(document_id)
    stored_task = await IngestionTaskRepository(db_session).get(task_id)
    assert stored_document is not None
    assert stored_task is not None
    assert stored_task.arq_job_id == str(task_id)
    assert stored_document.status == DocumentStatus.PENDING
    assert stored_task.status == TaskStatus.PENDING


async def test_service_persists_failed_state_after_enqueue_failure(
    db_session: AsyncSession,
) -> None:
    service, knowledge_base, storage = await make_service(
        db_session,
        FixedQueue(RuntimeError("redis unavailable")),
    )

    with pytest.raises(IngestionQueueUnavailableError):
        await service.upload(knowledge_base.id, "notes.md", "text/markdown", b"# notes")

    document = (await DocumentRepository(db_session).list_by_knowledge_base(knowledge_base.id))[0]
    task = await db_session.scalar(
        select(IngestionTask).where(IngestionTask.document_id == document.id)
    )
    assert task is not None
    await db_session.refresh(document)
    await db_session.refresh(task)
    assert document.status == DocumentStatus.FAILED
    assert task.status == TaskStatus.FAILED
    assert document.error == "redis unavailable"
    assert task.error == "redis unavailable"
    assert document.source_object_key in storage.objects


async def test_service_recovers_second_commit_failure_with_real_postgres(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge_base, _ = await make_service(db_session, FixedQueue())
    real_commit = db_session.commit
    commit_count = 0

    async def fail_second_commit() -> None:
        nonlocal commit_count
        commit_count += 1
        if commit_count == 2:
            raise RuntimeError("job id commit failed")
        await real_commit()

    monkeypatch.setattr(db_session, "commit", fail_second_commit)

    document, task = await service.upload(
        knowledge_base.id, "notes.md", "text/markdown", b"# notes"
    )
    document_id, task_id = document.id, task.id

    assert commit_count == 3
    db_session.expire_all()
    stored_document = await DocumentRepository(db_session).get(document_id)
    stored_task = await IngestionTaskRepository(db_session).get(task_id)
    assert stored_document is not None
    assert stored_task is not None
    assert stored_task.arq_job_id == str(task_id)
    assert stored_document.status == DocumentStatus.PENDING
    assert stored_task.status == TaskStatus.PENDING


async def test_upload_normalizes_unsafe_content_type(
    db_session: AsyncSession,
) -> None:
    service, knowledge_base, storage = await make_service(db_session, FixedQueue())

    document, _ = await service.upload(
        knowledge_base.id,
        "notes.md",
        "text/html\r\nX-Injected: yes",
        b"notes",
    )

    assert document.content_type == "application/octet-stream"
    assert storage.objects[document.source_object_key] == b"notes"


async def test_delete_rejects_active_document_before_external_cleanup(
    db_session: AsyncSession,
) -> None:
    service, knowledge_base, storage = await make_service(db_session, FixedQueue())
    document, _ = await service.upload(knowledge_base.id, "notes.md", "text/markdown", b"notes")

    with pytest.raises(DocumentNotRetryableError):
        await service.delete(knowledge_base.id, document.id)

    assert await DocumentRepository(db_session).get(document.id) is not None
    assert document.source_object_key in storage.objects


async def test_concurrent_retry_creates_only_one_active_task(
    db_session: AsyncSession,
) -> None:
    knowledge_base = KnowledgeBase(
        name=f"concurrent-{uuid.uuid4()}",
        description="",
        embedding_model="hashing",
        embedding_dimension=64,
    )
    document = Document(
        knowledge_base=knowledge_base,
        filename="notes.md",
        content_type="text/markdown",
        size_bytes=5,
        source_object_key="source",
        status=DocumentStatus.FAILED,
    )
    db_session.add_all([knowledge_base, document])
    await db_session.commit()

    engine = create_async_engine(get_settings().test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = MemoryStorage()

    async def run_retry() -> object:
        async with factory() as session:
            service = DocumentService(
                KnowledgeBaseRepository(session),
                DocumentRepository(session),
                IngestionTaskRepository(session),
                session,
                storage,
                FixedQueue(),
            )
            try:
                return await service.retry(knowledge_base.id, document.id)
            except DocumentNotRetryableError as exc:
                return exc

    try:
        results = await asyncio.gather(run_retry(), run_retry())
        assert sum(isinstance(result, IngestionTask) for result in results) == 1
        assert sum(isinstance(result, DocumentNotRetryableError) for result in results) == 1
        active_count = await db_session.scalar(
            select(func.count()).where(
                IngestionTask.document_id == document.id,
                IngestionTask.status.in_((TaskStatus.PENDING, TaskStatus.PROCESSING)),
            )
        )
        assert active_count == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("failure", ["index", "parsed", "source"])
async def test_delete_external_failure_preserves_real_database_record(
    db_session: AsyncSession,
    failure: str,
) -> None:
    knowledge_base = KnowledgeBase(
        name=f"cleanup-{uuid.uuid4()}",
        description="",
        embedding_model="hashing",
        embedding_dimension=64,
    )
    document = Document(
        knowledge_base=knowledge_base,
        filename="notes.md",
        content_type="text/markdown",
        size_bytes=5,
        source_object_key="source",
        parsed_object_key="parsed",
        status=DocumentStatus.COMPLETED,
    )
    db_session.add_all([knowledge_base, document])
    await db_session.commit()
    document_id = document.id
    knowledge_base_id = knowledge_base.id
    storage = MemoryStorage(fail_delete=failure if failure != "index" else None)
    storage.objects = {"source": b"notes", "parsed": b"{}"}
    index = MemoryIndex(fail=failure == "index")
    index.documents.add((knowledge_base_id, document_id))
    service = DocumentService(
        KnowledgeBaseRepository(db_session),
        DocumentRepository(db_session),
        IngestionTaskRepository(db_session),
        db_session,
        storage,
        FixedQueue(),
        index,
    )

    with pytest.raises(DocumentCleanupFailedError, match="Document cleanup failed"):
        await service.delete(knowledge_base_id, document_id)

    assert await DocumentRepository(db_session).get(document_id) is not None
