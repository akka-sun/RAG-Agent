import math

import pytest

from app.rag.embedding import HashingEmbedder


def test_hashing_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(dimensions=64)

    first = embedder.embed("Python async database")
    second = embedder.embed("Python async database")

    assert first == second
    assert len(first) == 64

    norm = math.sqrt(sum(value * value for value in first))

    assert norm == pytest.approx(1.0)


def test_hashing_embedder_supports_cjk_and_empty_text() -> None:
    embedder = HashingEmbedder(dimensions=64)

    assert embedder.embed("数据库") != (0.0,) * 64
    assert embedder.embed("   ") == (0.0,) * 64


def test_hashing_embedder_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        HashingEmbedder(dimensions=0)
