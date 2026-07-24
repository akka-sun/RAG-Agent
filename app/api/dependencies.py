from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.services.knowledge_base import (
    KnowledgeBaseService,
)
from app.services.rag import RAGService

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
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
