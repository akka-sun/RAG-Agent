from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from app.api import dependencies
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
