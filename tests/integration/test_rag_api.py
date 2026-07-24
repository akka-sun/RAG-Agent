import uuid

import pytest
from httpx import AsyncClient


async def create_knowledge_base(
    client: AsyncClient,
    name: str,
) -> str:
    response = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": name,
            "description": "",
            "embedding_model": "hashing-64",
            "embedding_dimension": 64,
        },
    )

    assert response.status_code == 201

    return str(response.json()["id"])


@pytest.mark.integration
async def test_rag_ingest_and_query_returns_citations(
    client: AsyncClient,
) -> None:
    knowledge_base_id = await create_knowledge_base(
        client,
        "RAG API",
    )

    ingest_response = await client.post(
        "/api/v1/rag/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "filename": "notes.md",
            "content": ("Python async applications use an event loop. PostgreSQL stores records."),
        },
    )

    assert ingest_response.status_code == 201

    document = ingest_response.json()
    assert document["chunk_count"] == 1

    query_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": knowledge_base_id,
            "query": "Python async",
            "top_k": 3,
        },
    )

    assert query_response.status_code == 200

    result = query_response.json()

    assert "[S1]" in result["answer"]
    assert result["sources"][0]["label"] == "S1"
    assert result["sources"][0]["document_id"] == document["document_id"]


@pytest.mark.integration
async def test_rag_isolates_knowledge_bases(
    client: AsyncClient,
) -> None:
    first_id = await create_knowledge_base(
        client,
        "First RAG",
    )
    second_id = await create_knowledge_base(
        client,
        "Second RAG",
    )

    ingest_response = await client.post(
        "/api/v1/rag/documents",
        json={
            "knowledge_base_id": first_id,
            "filename": "private.txt",
            "content": "private evidence",
        },
    )

    assert ingest_response.status_code == 201

    query_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": second_id,
            "query": "private evidence",
        },
    )

    assert query_response.status_code == 200
    assert query_response.json() == {
        "answer": "未找到相关证据。",
        "sources": [],
    }


@pytest.mark.integration
async def test_rag_rejects_missing_knowledge_base_and_invalid_file(
    client: AsyncClient,
) -> None:
    missing_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": str(uuid.uuid4()),
            "query": "anything",
        },
    )

    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "knowledge_base_not_found"

    knowledge_base_id = await create_knowledge_base(
        client,
        "Validation RAG",
    )

    invalid_response = await client.post(
        "/api/v1/rag/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "filename": "notes.pdf",
            "content": "content",
        },
    )

    assert invalid_response.status_code == 422
    assert invalid_response.json()["error"]["code"] == "validation_error"
