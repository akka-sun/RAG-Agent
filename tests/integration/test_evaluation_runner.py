import uuid
from collections.abc import Sequence

import pytest

from app.evaluation.dataset import EvaluationDataset, EvaluationQuestion
from app.evaluation.runner import EvaluationRunner
from app.rag.hybrid import RankedChunk, RetrievedChunk


class FakeEmbeddings:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(texts[0]))]]


class FakeStore:
    async def search_dense(
        self, knowledge_base_id: uuid.UUID, query_vector: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        del knowledge_base_id, query_vector, limit
        return [
            RetrievedChunk(
                chunk_id="chunk-a",
                document_id="00000000-0000-0000-0000-000000000001",
                text="alpha",
                rank=1,
                score=0.9,
                source="dense",
            )
        ]

    async def search_sparse(
        self, knowledge_base_id: uuid.UUID, query_text: str, limit: int
    ) -> list[RetrievedChunk]:
        del knowledge_base_id, query_text, limit
        return [
            RetrievedChunk(
                chunk_id="chunk-b",
                document_id="00000000-0000-0000-0000-000000000001",
                text="beta",
                rank=1,
                score=0.8,
                source="sparse",
            )
        ]


class FakeReranker:
    async def rerank(self, query: str, chunks: list[RankedChunk], limit: int) -> list[RankedChunk]:
        del query, limit
        return chunks


@pytest.mark.integration
async def test_runner_compares_retrieval_modes() -> None:
    runner = EvaluationRunner(
        knowledge_base_id=uuid.UUID("00000000-0000-0000-0000-000000000099"),
        store=FakeStore(),
        embeddings=FakeEmbeddings(),
        reranker=FakeReranker(),
    )
    dataset = EvaluationDataset(
        questions=[
            EvaluationQuestion(
                id="q1",
                question="retention",
                expected_document_ids=[
                    uuid.UUID("00000000-0000-0000-0000-000000000001"),
                ],
                expected_citations=[],
            )
        ]
    )

    result = await runner.run(dataset)

    assert {"dense", "bm25", "rrf", "rerank"} <= set(result.mode_results)
