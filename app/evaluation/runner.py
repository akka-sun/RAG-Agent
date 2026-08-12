from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.evaluation.dataset import EvaluationDataset, EvaluationQuestion
from app.evaluation.metrics import citation_hit_rate, mrr, recall_at_k
from app.rag.hybrid import RankedChunk, RetrievedChunk, dedupe_chunks, fuse_rrf


def _empty_strings() -> list[str]:
    return []


class EvaluationEmbeddingClient(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class EvaluationSearchStore(Protocol):
    async def search_dense(
        self, knowledge_base_id: uuid.UUID, query_vector: Sequence[float], limit: int
    ) -> list[RetrievedChunk]: ...

    async def search_sparse(
        self, knowledge_base_id: uuid.UUID, query_text: str, limit: int
    ) -> list[RetrievedChunk]: ...


class EvaluationReranker(Protocol):
    async def rerank(
        self, query: str, chunks: list[RankedChunk], limit: int
    ) -> list[RankedChunk]: ...


@dataclass(frozen=True, slots=True)
class ModeEvaluationResult:
    recall_at_k: float
    mrr: float
    citation_hit_rate: float
    retrieved_document_ids: list[str] = field(default_factory=_empty_strings)
    retrieved_citations: list[str] = field(default_factory=_empty_strings)


@dataclass(frozen=True, slots=True)
class QuestionEvaluationResult:
    question_id: str
    question: str
    mode_results: dict[str, ModeEvaluationResult]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    dataset_size: int
    mode_results: dict[str, ModeEvaluationResult]
    question_results: list[QuestionEvaluationResult]


class EvaluationRunner:
    def __init__(
        self,
        *,
        knowledge_base_id: uuid.UUID,
        store: EvaluationSearchStore,
        embeddings: EvaluationEmbeddingClient,
        reranker: EvaluationReranker,
        limit: int = 5,
    ) -> None:
        self._knowledge_base_id = knowledge_base_id
        self._store = store
        self._embeddings = embeddings
        self._reranker = reranker
        self._limit = limit

    async def run(self, dataset: EvaluationDataset) -> EvaluationResult:
        question_results: list[QuestionEvaluationResult] = []
        accumulated: dict[str, dict[str, float]] = {
            mode: {"recall_at_k": 0.0, "mrr": 0.0, "citation_hit_rate": 0.0}
            for mode in ("dense", "bm25", "rrf", "rerank")
        }

        for question in dataset.questions:
            result = await self._run_question(question)
            question_results.append(result)
            for mode, metrics in result.mode_results.items():
                accumulated[mode]["recall_at_k"] += metrics.recall_at_k
                accumulated[mode]["mrr"] += metrics.mrr
                accumulated[mode]["citation_hit_rate"] += metrics.citation_hit_rate

        count = max(len(question_results), 1)
        mode_results = {
            mode: ModeEvaluationResult(
                recall_at_k=metrics["recall_at_k"] / count,
                mrr=metrics["mrr"] / count,
                citation_hit_rate=metrics["citation_hit_rate"] / count,
            )
            for mode, metrics in accumulated.items()
        }
        return EvaluationResult(
            dataset_size=len(question_results),
            mode_results=mode_results,
            question_results=question_results,
        )

    async def _run_question(self, question: EvaluationQuestion) -> QuestionEvaluationResult:
        vectors = await self._embeddings.embed_texts([question.question])
        search_limit = max(self._limit * 2, self._limit)
        dense: list[RetrievedChunk] = []
        sparse: list[RetrievedChunk] = []
        fused: list[RankedChunk] = []
        reranked: list[RankedChunk] = []
        if vectors:
            dense = await self._store.search_dense(
                self._knowledge_base_id,
                vectors[0],
                search_limit,
            )
            sparse = await self._store.search_sparse(
                self._knowledge_base_id,
                question.question,
                search_limit,
            )
            fused = dedupe_chunks(fuse_rrf(dense, sparse, limit=search_limit))
            reranked = await self._reranker.rerank(question.question, fused, self._limit)

        mode_results = {
            "dense": _build_mode_result(dense[: self._limit], question),
            "bm25": _build_mode_result(sparse[: self._limit], question),
            "rrf": _build_mode_result(fused[: self._limit], question),
            "rerank": _build_mode_result(reranked[: self._limit], question),
        }
        return QuestionEvaluationResult(
            question_id=question.id,
            question=question.question,
            mode_results=mode_results,
        )


def _build_mode_result(
    chunks: Sequence[RetrievedChunk | RankedChunk],
    question: EvaluationQuestion,
) -> ModeEvaluationResult:
    retrieved_document_ids = [str(chunk.document_id) for chunk in chunks]
    retrieved_citations = [_citation_key(chunk.document_id, chunk.chunk_id) for chunk in chunks]
    expected_documents = {str(document_id) for document_id in question.expected_document_ids}
    expected_citations = {
        _citation_key(citation.document_id, citation.chunk_id)
        for citation in question.expected_citations
    }
    return ModeEvaluationResult(
        recall_at_k=recall_at_k(expected_documents, retrieved_document_ids, len(chunks)),
        mrr=mrr(expected_documents, retrieved_document_ids),
        citation_hit_rate=citation_hit_rate(expected_citations, set(retrieved_citations)),
        retrieved_document_ids=retrieved_document_ids,
        retrieved_citations=retrieved_citations,
    )


def _citation_key(document_id: uuid.UUID | str, chunk_id: str | None) -> str:
    base = str(document_id)
    if chunk_id:
        return f"{base}#{chunk_id}"
    return base
