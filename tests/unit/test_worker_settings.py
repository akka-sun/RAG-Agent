import asyncio

from app.config import Settings as CompatibilitySettings
from app.core.config import Settings
from app.infrastructure.milvus_store import MilvusDocumentIndex
from app.infrastructure.model_clients import EmbeddingClient
from app.parsers.router import ParserRouter
from app.worker import (
    WorkerSettings,
    build_document_index,
    build_ingestion_embedder,
    build_parser_router,
    health_job,
    ingest_document,
)


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
    assert WorkerSettings.functions == [health_job, ingest_document]
    assert WorkerSettings.redis_settings.host == "redis"
    assert WorkerSettings.redis_settings.port == 6379
    assert WorkerSettings.redis_settings.database == 0


def test_worker_builds_milvus_document_index() -> None:
    index = build_document_index(Settings())

    assert isinstance(index, MilvusDocumentIndex)


def test_worker_uses_external_embedding_client_when_api_key_is_configured() -> None:
    embedder = build_ingestion_embedder(
        Settings(
            embedding_base_url="https://api.example.test/v1",
            embedding_api_key="key",
            embedding_model="embedding-model",
        )
    )

    assert isinstance(embedder, EmbeddingClient)


def test_worker_builds_parser_router() -> None:
    router = build_parser_router(Settings())

    assert isinstance(router, ParserRouter)
    assert router.mineru is not None
    assert router.paddlex is not None


def test_worker_lifecycle_hooks_are_minimal_async_callables() -> None:
    context: dict[str, object] = {}

    assert asyncio.run(health_job(context)) == "ok"
    assert asyncio.run(WorkerSettings.on_startup(context)) is None
    assert asyncio.run(WorkerSettings.on_shutdown(context)) is None
