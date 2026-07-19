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