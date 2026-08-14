import asyncio
import os
import threading
from collections.abc import AsyncIterator, Iterator
from types import TracebackType
from typing import Any, Self, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

import app.main as main_module
from app.api import dependencies
from app.config import get_settings
from app.main import create_app
from app.schemas.health import ReadinessResponse, ServiceReadiness


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_app_uses_configured_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_AGENT_APP_NAME", "测试应用")
    monkeypatch.setenv("RAG_AGENT_DEBUG", "true")

    app = create_app()

    assert app.title == "测试应用"
    assert app.debug is True


def test_live_health_returns_process_status() -> None:
    client = TestClient(create_app())

    response = cast(
        Response,
        client.get("/api/v1/health/live"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class FakeReadinessService:
    async def check(self) -> ReadinessResponse:
        return ReadinessResponse(
            status="degraded",
            services={
                "postgresql": ServiceReadiness(status="healthy", latency_ms=1.25),
                "redis": ServiceReadiness(
                    status="unhealthy",
                    latency_ms=2.5,
                    error="Redis 连接失败",
                ),
                "minio": ServiceReadiness(status="healthy", latency_ms=3.75),
                "milvus": ServiceReadiness(status="healthy", latency_ms=4.0),
            },
        )


def test_ready_health_returns_exact_service_status_shape() -> None:
    application = create_app()
    application.dependency_overrides[dependencies.get_readiness_service] = FakeReadinessService
    client = TestClient(application)

    response = cast(
        Response,
        client.get("/api/v1/health/ready"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "services": {
            "postgresql": {"status": "healthy", "latency_ms": 1.25, "error": None},
            "redis": {
                "status": "unhealthy",
                "latency_ms": 2.5,
                "error": "Redis 连接失败",
            },
            "minio": {"status": "healthy", "latency_ms": 3.75, "error": None},
            "milvus": {"status": "healthy", "latency_ms": 4.0, "error": None},
        },
    }


def test_live_health_does_not_resolve_readiness_dependencies() -> None:
    def fail_if_resolved() -> FakeReadinessService:
        raise AssertionError("liveness must not resolve infrastructure dependencies")

    application = create_app()
    application.dependency_overrides[dependencies.get_readiness_service] = fail_if_resolved

    response = cast(
        Response,
        TestClient(application).get(  # pyright: ignore[reportUnknownMemberType]
            "/api/v1/health/live"
        ),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class FakeSession:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self.error = error
        self.release = release
        self.statements: list[str] = []
        self.close_count = 0
        self.execute_started = asyncio.Event()
        self.closed = asyncio.Event()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close_count += 1
        self.closed.set()

    async def execute(self, statement: object) -> None:
        self.statements.append(str(statement))
        self.execute_started.set()
        if self.release is not None:
            await self.release.wait()
        if self.error is not None:
            raise self.error


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.calls = 0

    def __call__(self) -> FakeSession:
        self.calls += 1
        return self.session


class FakeRedis:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.pinged = False
        self.closed = False

    async def ping(self) -> None:
        self.pinged = True
        if self.error is not None:
            raise self.error

    async def aclose(self) -> None:
        self.closed = True


class FakeMinio:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def bucket_exists(self, bucket: str) -> bool:
        self.calls.append(bucket)
        return False


class FakeMilvus:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []
        self.closed = False

    def has_collection(self, collection: str) -> bool:
        self.calls.append(collection)
        if self.error is not None:
            raise self.error
        return False

    def close(self) -> None:
        self.closed = True


class HealthyMinio(FakeMinio):
    def bucket_exists(self, bucket: str) -> bool:
        self.calls.append(bucket)
        return True


class HealthyMilvus(FakeMilvus):
    def has_collection(self, collection: str) -> bool:
        self.calls.append(collection)
        return True


def healthy_milvus_client(*, uri: str, token: str) -> HealthyMilvus:
    del uri, token
    return HealthyMilvus()


def use_probe_session(
    monkeypatch: pytest.MonkeyPatch,
    session: FakeSession,
) -> FakeSessionFactory:
    factory = FakeSessionFactory(session)
    monkeypatch.setattr(dependencies, "async_session_factory", factory, raising=False)
    return factory


@pytest.mark.asyncio
async def test_false_storage_checks_are_unhealthy_without_creating_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    session_factory = use_probe_session(monkeypatch, session)
    redis_instances: list[FakeRedis] = []
    minio = FakeMinio()
    milvus_instances: list[FakeMilvus] = []

    async def fake_create_pool(settings: object) -> FakeRedis:
        del settings
        redis = FakeRedis()
        redis_instances.append(redis)
        return redis

    def fake_milvus_client(*, uri: str, token: str) -> FakeMilvus:
        del uri, token
        milvus = FakeMilvus()
        milvus_instances.append(milvus)
        return milvus

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    monkeypatch.setattr(dependencies, "MilvusClient", fake_milvus_client)
    service = dependencies.get_readiness_service(cast(Any, minio))
    assert redis_instances == []
    assert milvus_instances == []

    result = await service.check()

    settings = get_settings()
    assert result.status == "degraded"
    assert result.services["minio"].error == "MinIO 连接失败"
    assert result.services["milvus"].error == "Milvus 连接失败"
    assert session_factory.calls == 1
    assert session.statements == ["SELECT 1"]
    assert session.close_count == 1
    assert minio.calls == [settings.minio_bucket]
    assert len(redis_instances) == 1
    assert redis_instances[0].pinged
    assert redis_instances[0].closed
    assert len(milvus_instances) == 1
    assert milvus_instances[0].calls == [settings.milvus_collection]
    assert milvus_instances[0].closed


@pytest.mark.parametrize("blocked_stage", ["constructor", "operation"])
@pytest.mark.asyncio
async def test_timed_out_milvus_worker_closes_once_after_late_completion(
    blocked_stage: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()
    closed = threading.Event()
    close_count = 0

    class BlockingMilvus:
        def has_collection(self, collection: str) -> bool:
            assert collection == get_settings().milvus_collection
            if blocked_stage == "operation":
                started.set()
                assert release.wait(timeout=2)
            return True

        def close(self) -> None:
            nonlocal close_count
            close_count += 1
            closed.set()

    async def fake_create_pool(settings: object) -> FakeRedis:
        del settings
        return FakeRedis()

    def fake_milvus_client(*, uri: str, token: str) -> BlockingMilvus:
        del uri, token
        if blocked_stage == "constructor":
            started.set()
            assert release.wait(timeout=2)
        return BlockingMilvus()

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    monkeypatch.setattr(dependencies, "MilvusClient", fake_milvus_client)
    session = FakeSession()
    use_probe_session(monkeypatch, session)
    service = dependencies.get_readiness_service(cast(Any, HealthyMinio()))

    check_task = asyncio.create_task(service.check())
    assert await asyncio.wait_for(asyncio.to_thread(started.wait, 0.2), timeout=0.3)
    try:
        result = await asyncio.wait_for(check_task, timeout=1.2)
        assert result.services["milvus"].error == "Milvus 连接失败"
        assert close_count == 0
    finally:
        release.set()

    assert await asyncio.wait_for(asyncio.to_thread(closed.wait, 0.2), timeout=0.3)
    assert close_count == 1


@pytest.mark.asyncio
async def test_failing_redis_and_milvus_probes_still_close_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = FakeRedis(ConnectionError("redis://admin:secret@redis:6379/0"))
    milvus = FakeMilvus(ConnectionError("http://token@milvus:19530"))

    async def fake_create_pool(settings: object) -> FakeRedis:
        del settings
        return redis

    def fake_milvus_client(*, uri: str, token: str) -> FakeMilvus:
        del uri, token
        return milvus

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    monkeypatch.setattr(dependencies, "MilvusClient", fake_milvus_client)
    session = FakeSession()
    use_probe_session(monkeypatch, session)
    service = dependencies.get_readiness_service(cast(Any, FakeMinio()))

    result = await service.check()

    assert result.status == "degraded"
    assert result.services["redis"].error == "Redis 连接失败"
    assert result.services["milvus"].error == "Milvus 连接失败"
    assert redis.closed
    assert milvus.closed
    assert "secret" not in result.model_dump_json()
    assert "token" not in result.model_dump_json()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (None, "healthy"),
        (ConnectionError("postgresql://admin:secret@db/internal"), "unhealthy"),
    ],
)
@pytest.mark.asyncio
async def test_postgresql_probe_closes_owned_session_on_success_and_error(
    error: Exception | None,
    expected_status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(error=error)
    factory = use_probe_session(monkeypatch, session)

    async def fake_create_pool(settings: object) -> FakeRedis:
        del settings
        return FakeRedis()

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    monkeypatch.setattr(
        dependencies,
        "MilvusClient",
        healthy_milvus_client,
    )
    service = dependencies.get_readiness_service(cast(Any, HealthyMinio()))

    result = await service.check()

    assert result.services["postgresql"].status == expected_status
    assert factory.calls == 1
    assert session.statements == ["SELECT 1"]
    assert session.close_count == 1
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_timed_out_postgresql_probe_closes_owned_session_after_late_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()
    session = FakeSession(release=release)
    factory = use_probe_session(monkeypatch, session)

    async def fake_create_pool(settings: object) -> FakeRedis:
        del settings
        return FakeRedis()

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    monkeypatch.setattr(
        dependencies,
        "MilvusClient",
        healthy_milvus_client,
    )
    service = dependencies.get_readiness_service(cast(Any, HealthyMinio()))
    check_task = asyncio.create_task(service.check())
    await asyncio.wait_for(session.execute_started.wait(), timeout=0.1)

    try:
        result = await asyncio.wait_for(check_task, timeout=1.2)
        assert result.services["postgresql"].status == "unhealthy"
        assert session.close_count == 0
    finally:
        release.set()

    await asyncio.wait_for(session.closed.wait(), timeout=0.1)
    assert factory.calls == 1
    assert session.close_count == 1


def test_ready_endpoint_does_not_resolve_request_scoped_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_session = FakeSession()
    factory = use_probe_session(monkeypatch, probe_session)

    async def fail_request_session() -> AsyncIterator[object]:
        raise AssertionError("readiness must not resolve a request-scoped database session")
        yield object()

    async def fake_create_pool(settings: object) -> FakeRedis:
        del settings
        return FakeRedis()

    monkeypatch.setattr(dependencies, "create_pool", fake_create_pool)
    monkeypatch.setattr(
        dependencies,
        "MilvusClient",
        healthy_milvus_client,
    )
    application = create_app()
    application.dependency_overrides[dependencies.get_session] = fail_request_session
    application.dependency_overrides[dependencies.get_minio_client] = HealthyMinio

    response = cast(
        Response,
        TestClient(application).get(  # pyright: ignore[reportUnknownMemberType]
            "/api/v1/health/ready"
        ),
    )

    assert response.status_code == 200
    assert response.json()["services"]["postgresql"]["status"] == "healthy"
    assert factory.calls == 1
    assert probe_session.close_count == 1


def test_live_health_does_not_create_any_database_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_probe_session_factory() -> None:
        raise AssertionError("liveness must not create a probe database session")

    async def fail_request_session() -> AsyncIterator[object]:
        raise AssertionError("liveness must not create a request database session")
        yield object()

    monkeypatch.setattr(
        dependencies,
        "async_session_factory",
        fail_probe_session_factory,
        raising=False,
    )
    application = create_app()
    application.dependency_overrides[dependencies.get_session] = fail_request_session

    response = cast(
        Response,
        TestClient(application).get(  # pyright: ignore[reportUnknownMemberType]
            "/api/v1/health/live"
        ),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_app_sets_up_agent_checkpoint_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, bool]] = []

    async def fake_setup_checkpointer(database_url: object, *, strict_msgpack: bool) -> None:
        calls.append((database_url, strict_msgpack))

    monkeypatch.delenv("LANGGRAPH_STRICT_MSGPACK", raising=False)
    monkeypatch.setattr(
        main_module,
        "setup_checkpointer",
        fake_setup_checkpointer,
        raising=False,
    )

    with TestClient(main_module.create_app()) as client:
        response = cast(
            Response,
            client.get("/api/v1/health/live"),  # pyright: ignore[reportUnknownMemberType]
        )

    assert response.status_code == 200
    assert os.environ["LANGGRAPH_STRICT_MSGPACK"] == "true"
    assert calls == [(get_settings().database_url, True)]
