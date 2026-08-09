import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.document import Document
from app.models.ingestion_task import IngestionTask, TaskStatus
from app.models.knowledge_base import KnowledgeBase
from app.repositories.documents import DocumentRepository
from app.repositories.ingestion_tasks import IngestionTaskRepository


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().test_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    "TRUNCATE TABLE message_citations, messages, conversations, "
                    "ingestion_tasks, documents, knowledge_bases"
                )
            )
            await session.commit()
            yield session
            await session.rollback()
            await session.execute(
                text(
                    "TRUNCATE TABLE message_citations, messages, conversations, "
                    "ingestion_tasks, documents, knowledge_bases"
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


def make_knowledge_base(name: str) -> KnowledgeBase:
    return KnowledgeBase(
        name=name,
        description="",
        embedding_model="hashing",
        embedding_dimension=16,
    )


def make_document(knowledge_base_id: uuid.UUID, filename: str) -> Document:
    return Document(
        knowledge_base_id=knowledge_base_id,
        filename=filename,
        content_type="text/plain",
        size_bytes=4,
        source_object_key=f"source/{filename}",
    )


async def test_document_repository_add_get_list_delete_and_kb_isolation(
    db_session: AsyncSession,
) -> None:
    first_kb = make_knowledge_base("first")
    second_kb = make_knowledge_base("second")
    db_session.add_all([first_kb, second_kb])
    await db_session.flush()
    first = make_document(first_kb.id, "first.txt")
    second = make_document(second_kb.id, "second.txt")
    repository = DocumentRepository(db_session)

    await repository.add(first)
    await repository.add(second)

    assert await repository.get(first.id) is first
    assert await repository.get(first.id, first_kb.id) is first
    assert await repository.get(first.id, second_kb.id) is None
    assert await repository.list_by_knowledge_base(first_kb.id) == [first]

    await repository.delete(first)
    assert await repository.get(first.id) is None


async def test_repositories_flush_without_committing(db_session: AsyncSession) -> None:
    knowledge_base = make_knowledge_base("not committed")
    db_session.add(knowledge_base)
    await db_session.flush()
    document = make_document(knowledge_base.id, "pending.txt")
    await DocumentRepository(db_session).add(document)
    task = IngestionTask(document_id=document.id)
    await IngestionTaskRepository(db_session).add(task)

    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as other_session:
            assert await DocumentRepository(other_session).get(document.id) is None
            assert await IngestionTaskRepository(other_session).get(task.id) is None
    finally:
        await engine.dispose()


async def test_ingestion_task_repository_get_claim_and_active(
    db_session: AsyncSession,
) -> None:
    knowledge_base = make_knowledge_base("claim")
    db_session.add(knowledge_base)
    await db_session.flush()
    document = make_document(knowledge_base.id, "claim.txt")
    await DocumentRepository(db_session).add(document)
    task = IngestionTask(document_id=document.id)
    repository = IngestionTaskRepository(db_session)
    await repository.add(task)

    assert await repository.get(task.id) is task
    assert await repository.has_active_task(document.id) is True

    claimed = await repository.claim_pending(task.id)
    assert claimed is not None
    assert claimed is task
    assert claimed.status == TaskStatus.PROCESSING
    assert claimed.started_at is not None
    assert await repository.claim_pending(task.id) is None

    task.status = TaskStatus.COMPLETED
    await db_session.flush()
    assert await repository.has_active_task(document.id) is False


async def test_claim_pending_is_atomic_across_sessions(db_session: AsyncSession) -> None:
    knowledge_base = make_knowledge_base("concurrent claim")
    db_session.add(knowledge_base)
    await db_session.flush()
    document = make_document(knowledge_base.id, "concurrent.txt")
    await DocumentRepository(db_session).add(document)
    task = IngestionTask(document_id=document.id)
    await IngestionTaskRepository(db_session).add(task)
    await db_session.commit()

    engine = create_async_engine(get_settings().test_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def claim() -> IngestionTask | None:
        async with session_factory() as session:
            claimed = await IngestionTaskRepository(session).claim_pending(task.id)
            await session.commit()
            return claimed

    try:
        results = await asyncio.gather(claim(), claim())
    finally:
        await engine.dispose()

    assert sum(result is not None for result in results) == 1
    assert next(result for result in results if result is not None).status == TaskStatus.PROCESSING


async def test_repository_preserves_foreign_key_and_status_constraints(
    db_session: AsyncSession,
) -> None:
    repository = DocumentRepository(db_session)
    with pytest.raises(IntegrityError):
        await repository.add(make_document(uuid.uuid4(), "missing-kb.txt"))

    await db_session.rollback()

    knowledge_base = make_knowledge_base("invalid status")
    db_session.add(knowledge_base)
    await db_session.flush()
    document = make_document(knowledge_base.id, "invalid.txt")
    document.status = "unknown"
    db_session.add(document)

    with pytest.raises(IntegrityError):
        await db_session.flush()
