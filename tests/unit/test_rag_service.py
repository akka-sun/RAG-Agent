import uuid
from unittest.mock import AsyncMock

import pytest

from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.schemas.rag import (
    RAGDocumentCreate,
    RAGQueryRequest,
)
from app.services.knowledge_base import KnowledgeBaseService
from app.services.rag import RAGService


@pytest.mark.asyncio
async def test_service_ingests_and_queries_with_stable_citations() -> None:
    knowledge_base_id = uuid.uuid4()
    knowledge_base_service = AsyncMock(spec=KnowledgeBaseService)
    service = RAGService(
        knowledge_base_service=knowledge_base_service,
        store=InMemoryVectorStore(),
        embedder=HashingEmbedder(),
        chunk_size=50,
        overlap=10,
    )

    document = await service.ingest(
        RAGDocumentCreate(
            knowledge_base_id=knowledge_base_id,
            filename="notes.md",
            content=("Python async applications use an event loop. PostgreSQL stores records."),
        )
    )

    response = await service.query(
        RAGQueryRequest(
            knowledge_base_id=knowledge_base_id,
            query="Python async",
            top_k=2,
        )
    )

    assert document.chunk_count == 2
    assert response.sources
    assert response.sources[0].label == "S1"
    assert response.sources[0].document_id == document.document_id
    assert "[S1]" in response.answer
    assert knowledge_base_service.get.await_count == 2


@pytest.mark.asyncio
async def test_service_returns_empty_result_without_indexed_evidence() -> None:
    knowledge_base_service = AsyncMock(spec=KnowledgeBaseService)
    service = RAGService(
        knowledge_base_service=knowledge_base_service,
        store=InMemoryVectorStore(),
        embedder=HashingEmbedder(),
    )

    response = await service.query(
        RAGQueryRequest(
            knowledge_base_id=uuid.uuid4(),
            query="missing",
        )
    )

    assert response.answer == "未找到相关证据。"
    assert response.sources == []
