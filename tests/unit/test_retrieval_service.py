import uuid

import pytest

from app.rag.hybrid import RankedChunk, RetrievedChunk
from app.services.retrieval import HybridRetrievalService


class FakeEmbeddingClient:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["refund policy"]
        return [[0.1, 0.2, 0.3]]


class FakeMilvusStore:
    def __init__(self) -> None:
        self.last_dense_filter_knowledge_base_id: uuid.UUID | None = None
        self.last_sparse_filter_knowledge_base_id: uuid.UUID | None = None

    async def search_dense(
        self, knowledge_base_id: uuid.UUID, query_vector: list[float], limit: int
    ) -> list[RetrievedChunk]:
        del query_vector, limit
        self.last_dense_filter_knowledge_base_id = knowledge_base_id
        return [
            RetrievedChunk(
                chunk_id="a",
                document_id=str(uuid.UUID("22222222-2222-2222-2222-222222222222")),
                text="refunds are available",
                rank=1,
                score=0.8,
                source="dense",
                metadata={"filename": "policy.md", "start": 0, "end": 21},
            )
        ]

    async def search_sparse(
        self, knowledge_base_id: uuid.UUID, query_text: str, limit: int
    ) -> list[RetrievedChunk]:
        del query_text, limit
        self.last_sparse_filter_knowledge_base_id = knowledge_base_id
        return [
            RetrievedChunk(
                chunk_id="a",
                document_id=str(uuid.UUID("22222222-2222-2222-2222-222222222222")),
                text="refunds are available",
                rank=1,
                score=10.0,
                source="sparse",
                metadata={"filename": "policy.md", "start": 0, "end": 21},
            )
        ]


class FakeReranker:
    async def rerank(self, query: str, chunks: list[RankedChunk], limit: int) -> list[RankedChunk]:
        del query
        return [
            RankedChunk(
                chunk_id=chunks[0].chunk_id,
                document_id=chunks[0].document_id,
                text=chunks[0].text,
                rrf_score=chunks[0].rrf_score,
                dense_rank=chunks[0].dense_rank,
                sparse_rank=chunks[0].sparse_rank,
                rerank_score=0.95,
                metadata=chunks[0].metadata,
            )
        ][:limit]


@pytest.mark.asyncio
async def test_hybrid_retrieval_filters_by_knowledge_base() -> None:
    store = FakeMilvusStore()
    service = HybridRetrievalService(
        store=store,
        embeddings=FakeEmbeddingClient(),
        reranker=FakeReranker(),
    )
    kb_id = uuid.uuid4()

    context = await service.query(knowledge_base_id=kb_id, query="refund policy", limit=5)

    assert store.last_dense_filter_knowledge_base_id == kb_id
    assert store.last_sparse_filter_knowledge_base_id == kb_id
    assert context.evidence[0].label == "S1"
    assert context.evidence[0].score == 0.95
    assert "[S1]" in context.answer
