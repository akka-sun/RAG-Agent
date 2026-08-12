import json

import httpx
import pytest

from app.infrastructure.model_clients import EmbeddingClient, RerankerClient
from app.rag.hybrid import RankedChunk


@pytest.mark.asyncio
async def test_embedding_client_posts_openai_compatible_payload() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = EmbeddingClient(
            base_url="https://api.example.test/v1",
            api_key="key",
            model="embedding-model",
            http_client=http_client,
        )

        vectors = await client.embed_texts(["hello"])

    assert vectors == [[0.1, 0.2]]
    assert captured_request is not None
    assert str(captured_request.url) == "https://api.example.test/v1/embeddings"
    assert captured_request.headers["authorization"] == "Bearer key"
    assert json.loads(captured_request.content) == {
        "model": "embedding-model",
        "input": ["hello"],
    }


@pytest.mark.asyncio
async def test_reranker_client_posts_documents_and_preserves_chunk_metadata() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.2},
                ]
            },
        )

    chunks = [
        RankedChunk(chunk_id="a", document_id="doc-a", text="first", rrf_score=0.5),
        RankedChunk(chunk_id="b", document_id="doc-b", text="second", rrf_score=0.4),
    ]

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = RerankerClient(
            base_url="https://rerank.example.test/v1",
            api_key="rerank-key",
            model="bge-reranker",
            http_client=http_client,
        )

        reranked = await client.rerank("refund policy", chunks, limit=1)

    assert [chunk.chunk_id for chunk in reranked] == ["b"]
    assert reranked[0].document_id == "doc-b"
    assert reranked[0].rerank_score == 0.95
    assert captured_request is not None
    assert str(captured_request.url) == "https://rerank.example.test/v1/rerank"
    assert captured_request.headers["authorization"] == "Bearer rerank-key"
    assert json.loads(captured_request.content) == {
        "model": "bge-reranker",
        "query": "refund policy",
        "documents": ["first", "second"],
        "top_n": 1,
    }
