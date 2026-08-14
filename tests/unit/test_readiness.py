from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from app.schemas.health import ServiceName
from app.services.readiness import ReadinessService

Probe = Callable[[], Awaitable[None]]


def make_service(
    *,
    postgresql: Probe,
    redis: Probe,
    minio: Probe,
    milvus: Probe,
    timeout_seconds: float = 0.1,
) -> ReadinessService:
    return ReadinessService(
        postgresql_probe=postgresql,
        redis_probe=redis,
        minio_probe=minio,
        milvus_probe=milvus,
        timeout_seconds=timeout_seconds,
    )


@pytest.mark.asyncio
async def test_check_starts_all_probes_before_waiting_for_results() -> None:
    started = {name: asyncio.Event() for name in ("postgresql", "redis", "minio", "milvus")}
    release = asyncio.Event()

    def concurrent_probe(name: str) -> Probe:
        async def probe() -> None:
            started[name].set()
            await release.wait()

        return probe

    service = make_service(
        postgresql=concurrent_probe("postgresql"),
        redis=concurrent_probe("redis"),
        minio=concurrent_probe("minio"),
        milvus=concurrent_probe("milvus"),
    )

    check_task = asyncio.create_task(service.check())
    await asyncio.wait_for(
        asyncio.gather(*(event.wait() for event in started.values())),
        timeout=0.05,
    )
    release.set()
    result = await check_task

    assert result.status == "healthy"
    assert list(result.services) == ["postgresql", "redis", "minio", "milvus"]
    assert all(service.status == "healthy" for service in result.services.values())


@pytest.mark.asyncio
async def test_one_failed_probe_does_not_suppress_peer_results() -> None:
    completed: set[str] = set()

    async def success(name: str) -> None:
        await asyncio.sleep(0)
        completed.add(name)

    async def failing_redis() -> None:
        raise ConnectionError("redis://admin:secret@redis.internal:6379/0")

    service = make_service(
        postgresql=lambda: success("postgresql"),
        redis=failing_redis,
        minio=lambda: success("minio"),
        milvus=lambda: success("milvus"),
    )

    result = await service.check()

    assert result.status == "degraded"
    assert completed == {"postgresql", "minio", "milvus"}
    assert result.services["postgresql"].status == "healthy"
    assert result.services["redis"].status == "unhealthy"
    assert result.services["redis"].error == "Redis 连接失败"
    assert "redis://" not in result.model_dump_json()
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_probe_timeout_is_bounded_and_reported_as_unhealthy() -> None:
    cancelled = asyncio.Event()

    async def success() -> None:
        return None

    async def blocked_milvus() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    service = make_service(
        postgresql=success,
        redis=success,
        minio=success,
        milvus=blocked_milvus,
        timeout_seconds=0.01,
    )

    result = await asyncio.wait_for(service.check(), timeout=0.1)

    assert cancelled.is_set()
    assert result.status == "degraded"
    assert result.services["milvus"].status == "unhealthy"
    assert result.services["milvus"].error == "Milvus 连接失败"
    assert result.services["postgresql"].status == "healthy"


@pytest.mark.asyncio
async def test_check_records_each_probe_latency_in_milliseconds() -> None:
    async def success() -> None:
        return None

    async def delayed_postgresql() -> None:
        await asyncio.sleep(0.01)

    service = make_service(
        postgresql=delayed_postgresql,
        redis=success,
        minio=success,
        milvus=success,
    )

    result = await service.check()

    assert result.services["postgresql"].latency_ms >= 5
    assert result.services["redis"].latency_ms >= 0


@pytest.mark.parametrize(
    ("failed_service", "expected_error", "secret"),
    [
        ("postgresql", "PostgreSQL 连接失败", "postgresql://root:pw@db/internal"),
        ("redis", "Redis 连接失败", "redis://root:pw@cache/0"),
        ("minio", "MinIO 连接失败", "minio-secret-key"),
        ("milvus", "Milvus 连接失败", "http://token@milvus:19530"),
    ],
)
@pytest.mark.asyncio
async def test_probe_errors_are_service_specific_and_sanitized(
    failed_service: ServiceName,
    expected_error: str,
    secret: str,
) -> None:
    async def success() -> None:
        return None

    async def failure() -> None:
        raise RuntimeError(secret)

    probes: dict[str, Probe] = {
        "postgresql": success,
        "redis": success,
        "minio": success,
        "milvus": success,
    }
    probes[failed_service] = failure
    service = make_service(
        postgresql=probes["postgresql"],
        redis=probes["redis"],
        minio=probes["minio"],
        milvus=probes["milvus"],
    )

    result = await service.check()

    assert result.services[failed_service].error == expected_error
    assert secret not in result.model_dump_json()
