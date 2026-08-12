from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from app.rag.hybrid import RetrievedChunk
from app.services.retrieval import HybridRetrievalService

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _empty_metadata() -> dict[str, object]:
    return {}


@dataclass(frozen=True, slots=True)
class BenchmarkDocument:
    document_id: uuid.UUID
    filename: str
    text: str
    vector: tuple[float, ...] = ()
    metadata: dict[str, object] = field(default_factory=_empty_metadata)


class InMemoryBenchmarkStore:
    """A deterministic store for public benchmark corpora.

    The application still supplies the real embedding and reranker clients;
    this store only avoids provisioning a second Milvus collection for a
    downloaded benchmark and makes each run isolated from production data.
    """

    def __init__(self) -> None:
        self._documents: dict[str, BenchmarkDocument] = {}
        self._token_counts: dict[str, Counter[str]] = {}
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 0.0

    def replace_documents(self, documents: Sequence[BenchmarkDocument]) -> None:
        self._documents = {str(document.document_id): document for document in documents}
        self._token_counts = {}
        self._document_frequency = Counter()
        total_length = 0
        for document in self._documents.values():
            tokens = Counter(_tokens(document.text))
            key = str(document.document_id)
            self._token_counts[key] = tokens
            total_length += sum(tokens.values())
            self._document_frequency.update(tokens.keys())
        self._average_length = total_length / max(len(self._documents), 1)

    async def search_dense(
        self, knowledge_base_id: uuid.UUID, query_vector: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        del knowledge_base_id
        ranked = sorted(
            self._documents.values(),
            key=lambda document: (
                -_cosine(query_vector, document.vector),
                str(document.document_id),
            ),
        )
        return [
            _retrieved_chunk(
                document, rank=index, score=_cosine(query_vector, document.vector), source="dense"
            )
            for index, document in enumerate(ranked[: max(limit, 0)], start=1)
        ]

    async def search_sparse(
        self, knowledge_base_id: uuid.UUID, query_text: str, limit: int
    ) -> list[RetrievedChunk]:
        del knowledge_base_id
        scores = [
            (
                document,
                _bm25_score(
                    query_text,
                    document,
                    self._token_counts,
                    self._document_frequency,
                    self._average_length,
                ),
            )
            for document in self._documents.values()
        ]
        ranked = sorted(scores, key=lambda item: (-item[1], str(item[0].document_id)))
        return [
            _retrieved_chunk(document, rank=index, score=score, source="sparse")
            for index, (document, score) in enumerate(ranked[: max(limit, 0)], start=1)
        ]

    def as_hybrid_service(self, *, embeddings: Any, reranker: Any) -> HybridRetrievalService:
        return HybridRetrievalService(store=self, embeddings=embeddings, reranker=reranker)


async def embed_documents(
    documents: Sequence[BenchmarkDocument],
    embeddings: Any,
    *,
    batch_size: int = 32,
) -> list[BenchmarkDocument]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    embedded: list[BenchmarkDocument] = []
    for start in range(0, len(documents), batch_size):
        batch = list(documents[start : start + batch_size])
        vectors = await embeddings.embed_texts([document.text for document in batch])
        if len(vectors) != len(batch):
            raise ValueError("embedding client returned a different number of vectors")
        embedded.extend(
            replace(document, vector=tuple(float(value) for value in vector))
            for document, vector in zip(batch, vectors, strict=True)
        )
    return embedded


def _retrieved_chunk(
    document: BenchmarkDocument,
    *,
    rank: int,
    score: float,
    source: str,
) -> RetrievedChunk:
    metadata = dict(document.metadata)
    metadata.setdefault("filename", document.filename)
    metadata.setdefault("start", 0)
    metadata.setdefault("end", len(document.text))
    return RetrievedChunk(
        chunk_id=f"{document.document_id}:0",
        document_id=str(document.document_id),
        text=document.text,
        rank=rank,
        score=score,
        source=source,
        metadata=metadata,
    )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _bm25_score(
    query: str,
    document: BenchmarkDocument,
    token_counts: dict[str, Counter[str]],
    document_frequency: Counter[str],
    average_length: float,
) -> float:
    query_tokens = _tokens(query)
    counts = token_counts.get(str(document.document_id), Counter())
    document_length = sum(counts.values())
    if not query_tokens or not counts:
        return 0.0
    score = 0.0
    total_documents = max(len(token_counts), 1)
    for token in query_tokens:
        term_frequency = counts.get(token, 0)
        if term_frequency == 0:
            continue
        frequency = document_frequency.get(token, 0)
        idf = math.log(1 + (total_documents - frequency + 0.5) / (frequency + 0.5))
        denominator = term_frequency + 1.5 * (
            1 - 0.75 + 0.75 * document_length / max(average_length, 1.0)
        )
        score += idf * term_frequency * 2.5 / denominator
    return score
