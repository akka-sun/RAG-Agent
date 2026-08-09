from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    rank: int
    score: float
    source: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RankedChunk:
    chunk_id: str
    document_id: str
    text: str
    rrf_score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


def rrf_score(rank: int, k: int = 60) -> float:
    if rank < 1:
        msg = "rank must be greater than or equal to 1"
        raise ValueError(msg)
    if k < 0:
        msg = "k must be greater than or equal to 0"
        raise ValueError(msg)
    return 1 / (k + rank)


def fuse_rrf(
    dense: Sequence[RetrievedChunk], sparse: Sequence[RetrievedChunk], limit: int
) -> list[RankedChunk]:
    fused: dict[str, RankedChunk] = {}

    for chunk in dense:
        fused[chunk.chunk_id] = _merge_retrieved_chunk(
            fused.get(chunk.chunk_id), chunk, source_rank="dense"
        )

    for chunk in sparse:
        fused[chunk.chunk_id] = _merge_retrieved_chunk(
            fused.get(chunk.chunk_id), chunk, source_rank="sparse"
        )

    ranked = sorted(
        fused.values(),
        key=lambda item: (
            -item.rrf_score,
            item.dense_rank if item.dense_rank is not None else 10**9,
            item.sparse_rank if item.sparse_rank is not None else 10**9,
            item.chunk_id,
        ),
    )
    return ranked[:limit]


def dedupe_chunks(chunks: Sequence[RankedChunk]) -> list[RankedChunk]:
    best_by_chunk_id: dict[str, RankedChunk] = {}

    for chunk in chunks:
        current = best_by_chunk_id.get(chunk.chunk_id)
        if current is None or chunk.rrf_score > current.rrf_score:
            best_by_chunk_id[chunk.chunk_id] = chunk

    return sorted(best_by_chunk_id.values(), key=lambda item: (-item.rrf_score, item.chunk_id))


def _merge_retrieved_chunk(
    current: RankedChunk | None, chunk: RetrievedChunk, *, source_rank: str
) -> RankedChunk:
    score = rrf_score(chunk.rank)
    if current is None:
        current = RankedChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            text=chunk.text,
            rrf_score=0,
            metadata=chunk.metadata,
        )

    if source_rank == "dense":
        return replace(
            current,
            rrf_score=current.rrf_score + score,
            dense_rank=chunk.rank,
            dense_score=chunk.score,
        )

    return replace(
        current,
        rrf_score=current.rrf_score + score,
        sparse_rank=chunk.rank,
        sparse_score=chunk.score,
    )
