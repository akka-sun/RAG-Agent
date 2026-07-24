from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.dependencies import get_rag_store
from app.config import get_settings
from app.db import get_session
from app.main import create_app
from app.rag.store import InMemoryVectorStore


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


@pytest.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    app = create_app()
    rag_store = InMemoryVectorStore()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    def override_rag_store() -> InMemoryVectorStore:
        return rag_store

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_rag_store] = override_rag_store

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client
