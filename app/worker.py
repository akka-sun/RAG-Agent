from arq.connections import RedisSettings
from minio import Minio
from redis import Redis

from app.core.config import get_settings
from app.db import async_session_factory
from app.infrastructure.object_storage import MinioObjectStorage
from app.infrastructure.redis_index import RedisDocumentIndex
from app.services.ingestion import IngestionService


async def ingest_document(ctx: dict[str, object], task_id: str, document_id: str) -> None:
    service = ctx["ingestion_service"]
    await service.run(task_id, document_id)  # type: ignore[union-attr]


async def health_job(ctx: dict[str, object]) -> str:
    return "ok"


async def on_startup(ctx: dict[str, object]) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    ctx["redis"] = redis
    ctx["ingestion_service"] = IngestionService(
        async_session_factory,
        MinioObjectStorage(minio, settings.minio_bucket),
        RedisDocumentIndex(redis),
    )


async def on_shutdown(ctx: dict[str, object]) -> None:
    redis = ctx.get("redis")
    if redis is not None:
        redis.close()  # type: ignore[union-attr]


class WorkerSettings:
    functions = [health_job, ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = staticmethod(on_startup)
    on_shutdown = staticmethod(on_shutdown)
