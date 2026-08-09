import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.observability import get_langfuse_tracer, get_trace_context, set_trace_context
from app.rag.hybrid import RankedChunk, RetrievedChunk, dedupe_chunks, fuse_rrf


def _empty_metadata() -> dict[str, object]:
    return {}


class EmbeddingClientProtocol(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class MilvusChunkStoreProtocol(Protocol):
    async def search_dense(
        self, knowledge_base_id: uuid.UUID, query_vector: list[float], limit: int
    ) -> list[RetrievedChunk]: ...

    async def search_sparse(
        self, knowledge_base_id: uuid.UUID, query_text: str, limit: int
    ) -> list[RetrievedChunk]: ...


class RerankerClientProtocol(Protocol):
    async def rerank(
        self, query: str, chunks: list[RankedChunk], limit: int
    ) -> list[RankedChunk]: ...


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    label: str
    document_id: uuid.UUID
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    score: float
    page_number: int | None = None
    section: str | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)


@dataclass(frozen=True, slots=True)
class RetrievalAnswerContext:
    answer: str
    evidence: list[RetrievalEvidence]


class HybridRetrievalService:
    def __init__(
        self,
        *,
        store: MilvusChunkStoreProtocol,
        embeddings: EmbeddingClientProtocol,
        reranker: RerankerClientProtocol,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._reranker = reranker

    async def query(
        self,
        *,
        knowledge_base_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> RetrievalAnswerContext:
        set_trace_context(
            stage="retrieve",
            knowledge_base_id=str(knowledge_base_id),
            retrieval_attempt=1,
        )
        logger.info("retrieval started")
        with get_langfuse_tracer().span(
            "retrieval.hybrid",
            get_trace_context().as_dict(),
            input={"query": query, "limit": limit},
        ):
            vectors = await self._embeddings.embed_texts([query])
            if not vectors:
                return _empty_context()

            search_limit = max(limit * 2, limit)
            dense = await self._store.search_dense(knowledge_base_id, vectors[0], search_limit)
            sparse = await self._store.search_sparse(knowledge_base_id, query, search_limit)
            fused = dedupe_chunks(fuse_rrf(dense, sparse, limit=search_limit))
            if not fused:
                return _empty_context()

        set_trace_context(stage="rerank", knowledge_base_id=str(knowledge_base_id))
        logger.info("reranking started")
        with get_langfuse_tracer().span(
            "retrieval.rerank",
            get_trace_context().as_dict(),
            input={"query": query, "candidates": len(fused), "limit": limit},
        ):
            reranked = await self._reranker.rerank(query, fused, limit)
        return _answer_context_from_chunks(reranked)


def _empty_context() -> RetrievalAnswerContext:
    return RetrievalAnswerContext(answer="未找到相关证据。", evidence=[])


def _answer_context_from_chunks(chunks: list[RankedChunk]) -> RetrievalAnswerContext:
    evidence = [
        RetrievalEvidence(
            label=f"S{index}",
            document_id=uuid.UUID(chunk.document_id),
            filename=str(chunk.metadata.get("filename", "")),
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            start=_int_metadata(chunk, "start"),
            end=_int_metadata(chunk, "end"),
            score=chunk.rerank_score if chunk.rerank_score is not None else chunk.rrf_score,
            page_number=_optional_int_metadata(chunk, "page_number"),
            section=_string_metadata(chunk, "section"),
            metadata=chunk.metadata,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]
    if not evidence:
        return _empty_context()

    answer_lines = [
        "根据检索到的资料：",
        *[f"[{item.label}] {item.text}" for item in evidence],
    ]
    return RetrievalAnswerContext(answer="\n".join(answer_lines), evidence=evidence)


def _int_metadata(chunk: RankedChunk, key: str) -> int:
    value = chunk.metadata.get(key, 0)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        return int(value)
    return 0


def _optional_int_metadata(chunk: RankedChunk, key: str) -> int | None:
    value = chunk.metadata.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        return int(value)
    return None


def _string_metadata(chunk: RankedChunk, key: str) -> str | None:
    value = chunk.metadata.get(key)
    if isinstance(value, str) and value:
        return value
    return None


logger = logging.getLogger(__name__)
