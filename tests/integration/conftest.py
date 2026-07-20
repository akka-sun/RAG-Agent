from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    test_engine = create_async_engine(get_settings().test_database_url)
    test_session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
    )

    try:
        async with test_session_factory() as session:
            await session.execute(text("TRUNCATE TABLE knowledge_bases"))
            await session.commit()

            yield session

            await session.rollback()
            await session.execute(text("TRUNCATE TABLE knowledge_bases"))
            await session.commit()
    finally:
        await test_engine.dispose()
