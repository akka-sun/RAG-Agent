from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy import ColumnDefault, DefaultClause, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import (
    Document,
    DocumentStatus,
    IngestionTask,
    TaskStage,
    TaskStatus,
)
from app.models.knowledge_base import KnowledgeBase


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


def make_knowledge_base(name: str = "model-test") -> KnowledgeBase:
    return KnowledgeBase(
        name=name,
        description="",
        embedding_model="test-model",
        embedding_dimension=3,
    )


def make_document(knowledge_base: KnowledgeBase) -> Document:
    return Document(
        knowledge_base=knowledge_base,
        filename="guide.md",
        content_type="text/markdown",
        size_bytes=42,
        source_object_key="source/guide.md",
    )


def test_model_columns_use_matching_python_and_server_defaults() -> None:
    document_columns = inspect(Document).columns
    task_columns = inspect(IngestionTask).columns

    assert cast(ColumnDefault, document_columns.status.default).arg == DocumentStatus.PENDING
    assert str(cast(DefaultClause, document_columns.status.server_default).arg) == "'pending'"
    assert cast(ColumnDefault, document_columns.chunk_count.default).arg == 0
    assert str(cast(DefaultClause, document_columns.chunk_count.server_default).arg) == "0"
    assert cast(ColumnDefault, task_columns.status.default).arg == TaskStatus.PENDING
    assert str(cast(DefaultClause, task_columns.status.server_default).arg) == "'pending'"
    assert cast(ColumnDefault, task_columns.stage.default).arg == TaskStage.QUEUED
    assert str(cast(DefaultClause, task_columns.stage.server_default).arg) == "'queued'"
    assert cast(ColumnDefault, task_columns.progress.default).arg == 0
    assert str(cast(DefaultClause, task_columns.progress.server_default).arg) == "0"


def test_relationships_preserve_document_and_task_history() -> None:
    knowledge_base = make_knowledge_base()
    document = make_document(knowledge_base)
    task = IngestionTask(document=document)

    assert document in knowledge_base.documents
    assert task in document.ingestion_tasks
    assert document.knowledge_base is knowledge_base
    assert task.document is document
    assert "delete" not in KnowledgeBase.documents.property.cascade
    assert "delete" not in Document.ingestion_tasks.property.cascade


@pytest.mark.parametrize("progress", [-1, 101])
async def test_progress_check_rejects_out_of_range_values(
    db_session: AsyncSession,
    progress: int,
) -> None:
    document = make_document(make_knowledge_base(f"progress-{progress}"))
    db_session.add(IngestionTask(document=document, progress=progress))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_database_defaults_are_applied_on_flush(db_session: AsyncSession) -> None:
    document = make_document(make_knowledge_base("defaults"))
    task = IngestionTask(document=document)
    db_session.add(task)
    await db_session.flush()

    assert document.status == DocumentStatus.PENDING
    assert document.chunk_count == 0
    assert task.status == TaskStatus.PENDING
    assert task.stage == TaskStage.QUEUED
    assert task.progress == 0


async def test_knowledge_base_delete_is_restricted_when_documents_exist(
    db_session: AsyncSession,
) -> None:
    knowledge_base = make_knowledge_base("restrict-kb")
    db_session.add(make_document(knowledge_base))
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM knowledge_bases WHERE id = :id"),
            {"id": knowledge_base.id},
        )
        await db_session.commit()


async def test_document_delete_is_restricted_when_task_history_exists(
    db_session: AsyncSession,
) -> None:
    document = make_document(make_knowledge_base("restrict-document"))
    db_session.add(IngestionTask(document=document))
    await db_session.commit()
    document_id = document.id

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM documents WHERE id = :id"),
            {"id": document_id},
        )
        await db_session.commit()


def test_status_values_are_stable_strings() -> None:
    assert [status.value for status in DocumentStatus] == [
        "pending",
        "processing",
        "completed",
        "failed",
    ]
    assert [status.value for status in TaskStatus] == [
        "pending",
        "processing",
        "completed",
        "failed",
    ]
    assert [stage.value for stage in TaskStage] == [
        "queued",
        "parsing",
        "chunking",
        "embedding",
        "indexing",
        "completed",
    ]
