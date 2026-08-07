from typing import Any

import pytest

from app.worker import ingest_document, on_shutdown


@pytest.mark.asyncio
async def test_worker_delegates_to_ingestion_service() -> None:
    class Service:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def run(self, task_id: str, document_id: str) -> None:
            self.calls.append((task_id, document_id))

    service = Service()
    await ingest_document({"ingestion_service": service}, "task-1", "doc-1")
    assert service.calls == [("task-1", "doc-1")]


@pytest.mark.asyncio
async def test_worker_propagates_service_error() -> None:
    class Service:
        async def run(self, *_args: str) -> None:
            raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await ingest_document({"ingestion_service": Service()}, "t", "d")


@pytest.mark.asyncio
async def test_shutdown_closes_redis_and_disposes_database_engine() -> None:
    class Redis:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Engine:
        def __init__(self) -> None:
            self.disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    redis, engine = Redis(), Engine()
    await on_shutdown({"redis": AnyRedis(redis), "engine": AnyEngine(engine)})
    assert redis.closed
    assert engine.disposed


def AnyRedis(value: object) -> Any:
    return value


def AnyEngine(value: object) -> Any:
    return value
