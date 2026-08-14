from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from app.schemas.health import ReadinessResponse, ServiceName, ServiceReadiness

Probe = Callable[[], Awaitable[None]]

_BACKGROUND_PROBES: set[asyncio.Future[None]] = set()

_ERROR_MESSAGES: dict[ServiceName, str] = {
    "postgresql": "PostgreSQL 连接失败",
    "redis": "Redis 连接失败",
    "minio": "MinIO 连接失败",
    "milvus": "Milvus 连接失败",
}


class ReadinessService:
    def __init__(
        self,
        *,
        postgresql_probe: Probe,
        redis_probe: Probe,
        minio_probe: Probe,
        milvus_probe: Probe,
        timeout_seconds: float = 1.0,
    ) -> None:
        self._probes: dict[ServiceName, Probe] = {
            "postgresql": postgresql_probe,
            "redis": redis_probe,
            "minio": minio_probe,
            "milvus": milvus_probe,
        }
        self._timeout_seconds = timeout_seconds

    async def check(self) -> ReadinessResponse:
        results = await asyncio.gather(
            *(
                self._check_probe(service_name, probe)
                for service_name, probe in self._probes.items()
            )
        )
        services = dict(zip(self._probes, results, strict=True))
        status = (
            "healthy"
            if all(service.status == "healthy" for service in services.values())
            else "degraded"
        )
        return ReadinessResponse(status=status, services=services)

    async def _check_probe(self, service_name: ServiceName, probe: Probe) -> ServiceReadiness:
        started_at = time.perf_counter()
        future = asyncio.ensure_future(probe())
        _BACKGROUND_PROBES.add(future)
        future.add_done_callback(_consume_background_probe)
        try:
            done, _ = await asyncio.wait({future}, timeout=self._timeout_seconds)
            if future not in done:
                raise TimeoutError
            future.result()
        except Exception:
            return ServiceReadiness(
                status="unhealthy",
                latency_ms=self._elapsed_ms(started_at),
                error=_ERROR_MESSAGES[service_name],
            )
        return ServiceReadiness(
            status="healthy",
            latency_ms=self._elapsed_ms(started_at),
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000, 2)


def _consume_background_probe(future: asyncio.Future[None]) -> None:
    _BACKGROUND_PROBES.discard(future)
    if not future.cancelled():
        future.exception()
