# pyright: reportMissingTypeStubs=false
from __future__ import annotations

import os
from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import URL

DatabaseUrl = str | URL


def ensure_langgraph_security_env(*, strict_msgpack: bool = True) -> None:
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true" if strict_msgpack else "false"


def create_async_checkpointer(
    database_url: DatabaseUrl,
    *,
    strict_msgpack: bool = True,
) -> AbstractAsyncContextManager[AsyncPostgresSaver]:
    ensure_langgraph_security_env(strict_msgpack=strict_msgpack)
    return AsyncPostgresSaver.from_conn_string(_psycopg_database_url(database_url))


async def setup_checkpointer(database_url: DatabaseUrl, *, strict_msgpack: bool = True) -> None:
    async with create_async_checkpointer(
        database_url,
        strict_msgpack=strict_msgpack,
    ) as checkpointer:
        await checkpointer.setup()


def _psycopg_database_url(database_url: DatabaseUrl) -> str:
    rendered_url = _render_database_url(database_url)
    if rendered_url.startswith("postgresql+asyncpg://"):
        return rendered_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if rendered_url.startswith("postgresql+psycopg://"):
        return rendered_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return rendered_url


def _render_database_url(database_url: DatabaseUrl) -> str:
    if isinstance(database_url, URL):
        return database_url.render_as_string(hide_password=False)
    return database_url
