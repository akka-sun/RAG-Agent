import asyncio

from app.config import Settings as CompatibilitySettings
from app.core.config import Settings
from app.worker import WorkerSettings, health_job


def test_compatibility_settings_import_uses_core_implementation() -> None:
    assert CompatibilitySettings is Settings


def test_settings_expose_async_ingestion_services() -> None:
    settings = Settings()

    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.minio_endpoint == "minio:9000"
    assert settings.minio_access_key == "rag-agent"
    assert settings.minio_secret_key == "rag-agent-secret"
    assert settings.minio_bucket == "rag-agent"


def test_worker_registers_health_job_and_redis_settings() -> None:
    assert WorkerSettings.functions == [health_job]
    assert WorkerSettings.redis_settings.host == "redis"
    assert WorkerSettings.redis_settings.port == 6379
    assert WorkerSettings.redis_settings.database == 0


def test_worker_lifecycle_hooks_are_minimal_async_callables() -> None:
    context: dict[str, object] = {}

    assert asyncio.run(health_job(context)) == "ok"
    assert asyncio.run(WorkerSettings.on_startup(context)) is None
    assert asyncio.run(WorkerSettings.on_shutdown(context)) is None
