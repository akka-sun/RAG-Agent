from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session


@pytest.mark.asyncio
async def test_get_session_yields_async_session() -> None:
    session_iterator: AsyncGenerator[AsyncSession, None] = get_session()

    session = await anext(session_iterator)

    assert isinstance(session, AsyncSession)
    await session_iterator.aclose()
