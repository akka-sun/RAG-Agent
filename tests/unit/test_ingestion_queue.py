from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api import dependencies
from app.api.errors import register_error_handlers
from app.core.exceptions import IngestionQueueUnavailableError
from app.infrastructure.queue import ArqIngestionQueue

TASK_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeRedis:
    def __init__(self, results: list[object | None]) -> None:
        self.results = results
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.closed = False

    async def enqueue_job(self, function: str, *args: object, **kwargs: object) -> object | None:
        self.calls.append((function, args, kwargs))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_enqueue_returns_job_id_and_passes_task_identifiers() -> None:
    redis = FakeRedis([SimpleNamespace(job_id=str(TASK_ID))])
    queue = ArqIngestionQueue(cast(Any, redis))

    result = await queue.enqueue(TASK_ID, DOCUMENT_ID)

    assert result == str(TASK_ID)
    assert redis.calls == [
        (
            "ingest_document",
            (str(TASK_ID), str(DOCUMENT_ID)),
            {"_job_id": str(TASK_ID)},
        )
    ]


@pytest.mark.asyncio
async def test_duplicate_job_is_reported_as_queue_unavailable() -> None:
    queue = ArqIngestionQueue(cast(Any, FakeRedis([None])))

    with pytest.raises(IngestionQueueUnavailableError):
        await queue.enqueue(TASK_ID, DOCUMENT_ID)


@pytest.mark.asyncio
async def test_connection_error_is_reported_as_queue_unavailable() -> None:
    error = ConnectionError("redis is down")
    queue = ArqIngestionQueue(cast(Any, FakeRedis([error])))

    with pytest.raises(IngestionQueueUnavailableError) as exc_info:
        await queue.enqueue(TASK_ID, DOCUMENT_ID)

    assert exc_info.value.__cause__ is error


@pytest.mark.asyncio
async def test_queue_dependency_closes_redis_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = FakeRedis([])

    async def fake_create_pool(settings: object) -> object:
        del settings
        return redis

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    dependency = cast(AsyncIterator[ArqIngestionQueue], dependencies.get_ingestion_queue())

    queue = await anext(dependency)
    assert isinstance(queue, ArqIngestionQueue)
    assert not redis.closed

    with pytest.raises(StopAsyncIteration):
        await anext(dependency)
    assert redis.closed


@pytest.mark.asyncio
async def test_queue_dependency_maps_pool_creation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ConnectionError("redis is down")

    async def fake_create_pool(settings: object) -> object:
        del settings
        raise error

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    dependency = cast(AsyncIterator[ArqIngestionQueue], dependencies.get_ingestion_queue())

    with pytest.raises(IngestionQueueUnavailableError) as exc_info:
        await anext(dependency)

    assert exc_info.value.__cause__ is error


def test_pool_creation_failure_uses_queue_unavailable_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create_pool(settings: object) -> object:
        del settings
        raise ConnectionError("redis is down")

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/enqueue")
    async def enqueue(  # pyright: ignore[reportUnusedFunction]
        queue: dependencies.IngestionQueueDependency,
    ) -> None:
        del queue

    response = cast(
        Response,
        TestClient(app).get("/enqueue"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ingestion_queue_unavailable"


@pytest.mark.asyncio
async def test_queue_dependency_does_not_map_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create_pool(settings: object) -> object:
        del settings
        raise asyncio.CancelledError

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    dependency = cast(AsyncIterator[ArqIngestionQueue], dependencies.get_ingestion_queue())

    with pytest.raises(asyncio.CancelledError):
        await anext(dependency)
