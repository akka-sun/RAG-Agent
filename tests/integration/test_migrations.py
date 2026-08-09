from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def test_migration_creates_knowledge_bases_table() -> None:
    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'knowledge_bases'"
                    ")"
                )
            )
            assert result.scalar_one() is True
    finally:
        await engine.dispose()


async def test_migration_creates_unique_active_task_index() -> None:
    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND indexname = 'uq_ingestion_tasks_active_document'"
                )
            )
            definition = result.scalar_one()
            assert "UNIQUE INDEX" in definition
            assert "status" in definition
            assert "pending" in definition
            assert "processing" in definition
    finally:
        await engine.dispose()


async def test_migration_creates_conversation_message_and_citation_tables() -> None:
    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name IN ('conversations', 'messages', 'message_citations')"
                )
            )
            assert {row.table_name for row in result} == {
                "conversations",
                "messages",
                "message_citations",
            }
    finally:
        await engine.dispose()


async def test_migration_creates_message_sequence_number_default() -> None:
    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'messages' "
                    "AND column_name = 'sequence_number'"
                )
            )
            column_default = result.scalar_one()
            assert "nextval" in column_default
            assert "messages_sequence_number_seq" in column_default
    finally:
        await engine.dispose()


async def test_migration_creates_document_parser_name_default() -> None:
    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'documents' "
                    "AND column_name = 'parser_name'"
                )
            )
            assert result.scalar_one() == "'local'::character varying"
    finally:
        await engine.dispose()
