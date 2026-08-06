import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IngestionQueueUnavailableError
from app.models.document import DocumentStatus
from app.models.ingestion_task import IngestionTask, TaskStatus
from app.models.knowledge_base import KnowledgeBase
from app.repositories.documents import DocumentRepository
from app.repositories.ingestion_tasks import IngestionTaskRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.documents import DocumentService


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        del self.objects[key]


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
