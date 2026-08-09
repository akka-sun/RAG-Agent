from app.rag.hybrid import RankedChunk, RetrievedChunk, dedupe_chunks, fuse_rrf, rrf_score


def test_rrf_score_uses_rank_offset_without_raw_score() -> None:
    assert rrf_score(rank=1, k=60) == 1 / 61
    assert rrf_score(rank=2, k=60) == 1 / 62


def test_fuse_rrf_prefers_chunk_present_in_both_paths() -> None:
    dense = [
        RetrievedChunk(
            chunk_id="a",
            document_id="d1",
            text="dense a",
            rank=1,
            score=0.9,
            source="dense",
        ),
        RetrievedChunk(
            chunk_id="b",
            document_id="d1",
            text="dense b",
            rank=2,
            score=0.8,
            source="dense",
        ),
    ]
    sparse = [
        RetrievedChunk(
            chunk_id="b",
            document_id="d1",
            text="sparse b",
            rank=1,
            score=12.0,
            source="sparse",
        ),
        RetrievedChunk(
            chunk_id="c",
            document_id="d1",
            text="sparse c",
            rank=2,
            score=8.0,
            source="sparse",
        ),
    ]

    fused = fuse_rrf(dense, sparse, limit=3)

    assert [item.chunk_id for item in fused] == ["b", "a", "c"]
    assert fused[0].dense_rank == 2
    assert fused[0].sparse_rank == 1
    assert fused[0].text == "dense b"


def test_dedupe_chunks_keeps_highest_ranked_chunk() -> None:
    chunks = [
        RankedChunk(chunk_id="a", document_id="d1", text="first", rrf_score=0.03),
        RankedChunk(chunk_id="a", document_id="d1", text="second", rrf_score=0.01),
    ]

    assert dedupe_chunks(chunks)[0].text == "first"
