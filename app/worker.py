from typing import Any, cast

from arq.connections import RedisSettings
from minio import Minio
from redis import Redis

from app.core.config import Settings, get_settings
from app.db import async_session_factory, engine
from app.infrastructure.milvus_store import MilvusChunkStore, MilvusDocumentIndex
from app.infrastructure.model_clients import EmbeddingClient
from app.infrastructure.object_storage import MinioObjectStorage
from app.rag.embedding import HashingEmbedder
from app.services.ingestion import IngestionService


async def ingest_document(ctx: dict[str, object], task_id: str, document_id: str) -> None:
    service = ctx["ingestion_service"]
    await service.run(task_id, document_id)  # type: ignore[union-attr]


async def health_job(ctx: dict[str, object]) -> str:
    return "ok"


def build_document_index(settings: Settings) -> MilvusDocumentIndex:
    return MilvusDocumentIndex(
        MilvusChunkStore(
            uri=settings.milvus_uri,
            token=settings.milvus_token,
            collection_name=settings.milvus_collection,
            embedding_dimension=settings.embedding_dimension,
        )
    )


def build_ingestion_embedder(settings: Settings) -> EmbeddingClient | HashingEmbedder:
    if settings.app_env == "production" or settings.embedding_api_key:
        return EmbeddingClient(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
        )
    return HashingEmbedder(dimensions=settings.embedding_dimension)


async def on_startup(ctx: dict[str, object]) -> None:
    settings = get_settings()
    redis = cast(Any, Redis).from_url(settings.redis_url)
    minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    ctx["redis"] = redis
    ctx["engine"] = engine
    ctx["ingestion_service"] = IngestionService(
        async_session_factory,
        MinioObjectStorage(minio, settings.minio_bucket),
        build_document_index(settings),
        build_ingestion_embedder(settings),
    )


async def on_shutdown(ctx: dict[str, object]) -> None:
    redis = ctx.get("redis")
    if redis is not None:
        redis.close()  # type: ignore[union-attr]
    database_engine = ctx.get("engine")
    if database_engine is not None:
        await database_engine.dispose()  # type: ignore[union-attr]


class WorkerSettings:
    functions = [health_job, ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = staticmethod(on_startup)
    on_shutdown = staticmethod(on_shutdown)
