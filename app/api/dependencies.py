from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from arq.connections import RedisSettings, create_pool
from fastapi import Depends
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import IngestionQueueUnavailableError
from app.db import get_session
from app.infrastructure.object_storage import MinioObjectStorage, ObjectStorage
from app.infrastructure.queue import ArqIngestionQueue, IngestionQueue
from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.repositories.documents import DocumentRepository
from app.repositories.ingestion_tasks import IngestionTaskRepository
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.services.documents import DocumentService
from app.services.knowledge_base import (
    KnowledgeBaseService,
)
from app.services.rag import RAGService

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


async def get_ingestion_queue() -> AsyncIterator[IngestionQueue]:
    try:
        redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    except Exception as exc:
        raise IngestionQueueUnavailableError("Ingestion queue is unavailable") from exc
    try:
        yield ArqIngestionQueue(redis)
    finally:
        await redis.aclose()


IngestionQueueDependency = Annotated[
    IngestionQueue,
    Depends(get_ingestion_queue),
]


class DocumentIngestionQueue:
    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings

    async def enqueue(self, task_id: UUID, document_id: UUID) -> str:
        try:
            redis = await create_pool(self._settings)
        except Exception as exc:
            raise IngestionQueueUnavailableError("Ingestion queue is unavailable") from exc
        try:
            return await ArqIngestionQueue(redis).enqueue(task_id, document_id)
        finally:
            await redis.aclose()


def get_document_ingestion_queue() -> IngestionQueue:
    return DocumentIngestionQueue(
        RedisSettings.from_dsn(get_settings().redis_url),
    )


DocumentIngestionQueueDependency = Annotated[
    IngestionQueue,
    Depends(get_document_ingestion_queue),
]


def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    return MinioObjectStorage(client, settings.minio_bucket)


ObjectStorageDependency = Annotated[
    ObjectStorage,
    Depends(get_object_storage),
]


def get_document_service(
    session: SessionDependency,
    storage: ObjectStorageDependency,
    queue: DocumentIngestionQueueDependency,
) -> DocumentService:
    return DocumentService(
        knowledge_bases=KnowledgeBaseRepository(session),
        documents=DocumentRepository(session),
        tasks=IngestionTaskRepository(session),
        session=session,
        storage=storage,
        queue=queue,
    )


DocumentServiceDependency = Annotated[
    DocumentService,
    Depends(get_document_service),
]


def get_knowledge_base_service(
    session: SessionDependency,
) -> KnowledgeBaseService:
    repository = KnowledgeBaseRepository(session)
    return KnowledgeBaseService(
        repository,
        session,
    )


KnowledgeBaseServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]


@lru_cache
def get_rag_store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


@lru_cache
def get_hashing_embedder() -> HashingEmbedder:
    return HashingEmbedder(dimensions=64)


RAGStoreDependency = Annotated[
    InMemoryVectorStore,
    Depends(get_rag_store),
]

HashingEmbedderDependency = Annotated[
    HashingEmbedder,
    Depends(get_hashing_embedder),
]


def get_rag_service(
    knowledge_base_service: KnowledgeBaseServiceDependency,
    store: RAGStoreDependency,
    embedder: HashingEmbedderDependency,
) -> RAGService:
    return RAGService(
        knowledge_base_service=knowledge_base_service,
        store=store,
        embedder=embedder,
    )


RAGServiceDependency = Annotated[
    RAGService,
    Depends(get_rag_service),
]
