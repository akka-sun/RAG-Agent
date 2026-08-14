import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated, Protocol, cast
from uuid import UUID

from arq.connections import RedisSettings, create_pool
from fastapi import Depends
from minio import Minio
from pymilvus import MilvusClient  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.checkpoint import create_async_checkpointer
from app.agent.graph import build_agent_graph
from app.agent.tools import RetrievalTool
from app.config import get_settings
from app.core.exceptions import IngestionQueueUnavailableError
from app.db import get_session
from app.infrastructure.chat_client import ChatClient
from app.infrastructure.milvus_store import MilvusChunkStore, MilvusDocumentIndex
from app.infrastructure.model_clients import EmbeddingClient, RerankerClient
from app.infrastructure.object_storage import MinioObjectStorage, ObjectStorage
from app.infrastructure.queue import ArqIngestionQueue, IngestionQueue
from app.parsers.router import ParserRouter
from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.repositories.conversations import ConversationRepository
from app.repositories.documents import DocumentRepository
from app.repositories.ingestion_tasks import IngestionTaskRepository
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.repositories.messages import MessageRepository
from app.services.agent_chat import AgentChatService, AgentGraphProtocol
from app.services.conversations import ConversationService
from app.services.documents import DocumentService
from app.services.knowledge_base import (
    KnowledgeBaseService,
)
from app.services.rag import RAGService
from app.services.readiness import ReadinessService
from app.services.retrieval import HybridRetrievalService
from app.services.sse_chat import (
    ConversationRepositoryProtocol as SSEConversationRepositoryProtocol,
)
from app.services.sse_chat import SSEChatService

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


def get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )


MinioClientDependency = Annotated[
    Minio,
    Depends(get_minio_client),
]


class _RedisProbeClient(Protocol):
    async def ping(self) -> object: ...

    async def aclose(self) -> None: ...


class _MilvusProbeClient(Protocol):
    def has_collection(self, collection_name: str, /) -> bool: ...

    def close(self) -> None: ...


def get_object_storage(client: MinioClientDependency) -> ObjectStorage:
    return MinioObjectStorage(client, get_settings().minio_bucket)


ObjectStorageDependency = Annotated[
    ObjectStorage,
    Depends(get_object_storage),
]


def get_readiness_service(
    session: SessionDependency,
    minio: MinioClientDependency,
) -> ReadinessService:
    settings = get_settings()

    async def postgresql_probe() -> None:
        await session.execute(text("SELECT 1"))

    async def redis_probe() -> None:
        redis = cast(
            _RedisProbeClient,
            await create_pool(RedisSettings.from_dsn(settings.redis_url)),
        )
        try:
            await redis.ping()
        finally:
            await redis.aclose()

    async def minio_probe() -> None:
        exists = await asyncio.to_thread(minio.bucket_exists, settings.minio_bucket)
        if not exists:
            raise RuntimeError("configured MinIO bucket does not exist")

    async def milvus_probe() -> None:
        def check_collection() -> None:
            milvus = cast(
                _MilvusProbeClient,
                MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token or ""),
            )
            try:
                if not milvus.has_collection(settings.milvus_collection):
                    raise RuntimeError("configured Milvus collection does not exist")
            finally:
                milvus.close()

        await asyncio.to_thread(check_collection)

    return ReadinessService(
        postgresql_probe=postgresql_probe,
        redis_probe=redis_probe,
        minio_probe=minio_probe,
        milvus_probe=milvus_probe,
    )


ReadinessServiceDependency = Annotated[
    ReadinessService,
    Depends(get_readiness_service),
]


async def get_document_index() -> MilvusDocumentIndex:
    store = await get_milvus_chunk_store()
    return MilvusDocumentIndex(store)


DocumentIndexDependency = Annotated[
    MilvusDocumentIndex,
    Depends(get_document_index),
]


def get_document_service(
    session: SessionDependency,
    storage: ObjectStorageDependency,
    queue: DocumentIngestionQueueDependency,
    index: DocumentIndexDependency,
) -> DocumentService:
    settings = get_settings()
    return DocumentService(
        knowledge_bases=KnowledgeBaseRepository(session),
        documents=DocumentRepository(session),
        tasks=IngestionTaskRepository(session),
        session=session,
        storage=storage,
        queue=queue,
        index=index,
        parser_router=ParserRouter(default_pdf_parser=settings.default_pdf_parser),
    )


DocumentServiceDependency = Annotated[
    DocumentService,
    Depends(get_document_service),
]


def get_knowledge_base_service(
    session: SessionDependency,
) -> KnowledgeBaseService:
    settings = get_settings()
    repository = KnowledgeBaseRepository(session)
    return KnowledgeBaseService(
        repository,
        session,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
    )


KnowledgeBaseServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]


def get_conversation_service(
    session: SessionDependency,
) -> ConversationService:
    return ConversationService(
        knowledge_bases=KnowledgeBaseRepository(session),
        conversations=ConversationRepository(session),
        messages=MessageRepository(session),
        session=session,
    )


ConversationServiceDependency = Annotated[
    ConversationService,
    Depends(get_conversation_service),
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


@lru_cache
def get_milvus_chunk_store_instance() -> MilvusChunkStore:
    settings = get_settings()
    return MilvusChunkStore(
        uri=settings.milvus_uri,
        token=settings.milvus_token,
        collection_name=settings.milvus_collection,
        embedding_dimension=settings.embedding_dimension,
    )


async def get_milvus_chunk_store() -> MilvusChunkStore:
    store = get_milvus_chunk_store_instance()
    await store.ensure_collection()
    return store


MilvusChunkStoreDependency = Annotated[
    MilvusChunkStore,
    Depends(get_milvus_chunk_store),
]


def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    return EmbeddingClient(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
    )


EmbeddingClientDependency = Annotated[
    EmbeddingClient,
    Depends(get_embedding_client),
]


def get_chat_client() -> ChatClient:
    settings = get_settings()
    return ChatClient(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        model=settings.chat_model,
    )


ChatClientDependency = Annotated[
    ChatClient,
    Depends(get_chat_client),
]


def get_reranker_client() -> RerankerClient:
    settings = get_settings()
    return RerankerClient(
        base_url=settings.rerank_base_url,
        api_key=settings.rerank_api_key,
        model=settings.rerank_model,
    )


RerankerClientDependency = Annotated[
    RerankerClient,
    Depends(get_reranker_client),
]


def get_retrieval_service(
    store: MilvusChunkStoreDependency,
    embeddings: EmbeddingClientDependency,
    reranker: RerankerClientDependency,
) -> HybridRetrievalService:
    return HybridRetrievalService(
        store=store,
        embeddings=embeddings,
        reranker=reranker,
    )


HybridRetrievalServiceDependency = Annotated[
    HybridRetrievalService,
    Depends(get_retrieval_service),
]


async def get_agent_chat_service(
    chat_client: ChatClientDependency,
    retrieval_service: HybridRetrievalServiceDependency,
) -> AsyncIterator[AgentChatService]:
    settings = get_settings()
    retrieval_tool = RetrievalTool(service=retrieval_service, limit=3)
    async with create_async_checkpointer(
        settings.database_url,
        strict_msgpack=settings.langgraph_strict_msgpack,
    ) as checkpointer:
        graph = build_agent_graph(
            chat_client=chat_client,
            retrieval_tool=retrieval_tool,
            max_retrievals=settings.agent_max_retrievals,
            checkpointer=checkpointer,
        )
        yield AgentChatService(graph=cast(AgentGraphProtocol, graph))


AgentChatServiceDependency = Annotated[
    AgentChatService,
    Depends(get_agent_chat_service),
]


def get_sse_chat_service(
    session: SessionDependency,
    agent: AgentChatServiceDependency,
) -> SSEChatService:
    return SSEChatService(
        conversations=cast(SSEConversationRepositoryProtocol, ConversationRepository(session)),
        messages=MessageRepository(session),
        agent=agent,
        session=session,
    )


SSEChatServiceDependency = Annotated[
    SSEChatService,
    Depends(get_sse_chat_service),
]
