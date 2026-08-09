import os

import pytest

from app.config import Settings
from app.infrastructure.model_clients import EmbeddingClient, RerankerClient
from app.rag.hybrid import RankedChunk


def external_tests_enabled() -> bool:
    return os.getenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", "").casefold() == "true"


def skip_unless_external_enabled(*required_values: str) -> None:
    if not external_tests_enabled():
        pytest.skip("set RAG_AGENT_EXTERNAL_TESTS_ENABLED=true to call real external APIs")
    if any(not value for value in required_values):
        pytest.skip("external API test credentials are not fully configured")


@pytest.mark.external
@pytest.mark.asyncio
async def test_embedding_client_calls_real_api() -> None:
    settings = Settings()
    skip_unless_external_enabled(
        settings.embedding_base_url,
        settings.embedding_api_key,
        settings.embedding_model,
    )
    client = EmbeddingClient(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
    )

    vectors = await client.embed_texts(["RAG external embedding smoke test"])

    assert vectors
    assert len(vectors[0]) > 0


@pytest.mark.external
@pytest.mark.asyncio
async def test_reranker_client_calls_real_api() -> None:
    settings = Settings()
    skip_unless_external_enabled(
        settings.rerank_base_url,
        settings.rerank_api_key,
        settings.rerank_model,
    )
    client = RerankerClient(
        base_url=settings.rerank_base_url,
        api_key=settings.rerank_api_key,
        model=settings.rerank_model,
    )
    chunks = [
        RankedChunk(
            chunk_id="relevant",
            document_id="doc-1",
            text="Refunds are available within thirty days.",
            rrf_score=0.1,
        ),
        RankedChunk(
            chunk_id="irrelevant",
            document_id="doc-2",
            text="The office kitchen closes at six.",
            rrf_score=0.09,
        ),
    ]

    reranked = await client.rerank("How long do refunds take?", chunks, limit=2)

    assert reranked
    assert reranked[0].rerank_score is not None
