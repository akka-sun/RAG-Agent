import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.agent.state import AgentEvidence
from app.api import dependencies
from app.services.retrieval import RetrievalAnswerContext, RetrievalEvidence

DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class FakeHybridRetrievalService:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, str, int]] = []

    async def query(
        self, *, knowledge_base_id: uuid.UUID, query: str, limit: int
    ) -> RetrievalAnswerContext:
        self.calls.append((knowledge_base_id, query, limit))
        if query == "missing evidence":
            return RetrievalAnswerContext(answer="未找到相关证据。", evidence=[])
        return RetrievalAnswerContext(
            answer="根据检索到的资料：\n[S1] refunds are available",
            evidence=[
                RetrievalEvidence(
                    label="S1",
                    document_id=DOCUMENT_ID,
                    filename="policy.md",
                    chunk_id="chunk-1",
                    text="refunds are available",
                    start=0,
                    end=21,
                    score=0.95,
                )
            ],
        )


class FakeAgentChatService:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, str]] = []

    async def answer(self, *, knowledge_base_id: uuid.UUID, query: str) -> SimpleNamespace:
        self.calls.append((knowledge_base_id, query))
        return SimpleNamespace(
            content="agent answer",
            citations=[
                AgentEvidence(
                    label="S1",
                    document_id=DOCUMENT_ID,
                    filename="policy.md",
                    chunk_id="chunk-1",
                    text="refunds are available",
                    start=0,
                    end=21,
                    score=0.95,
                )
            ],
        )


async def create_knowledge_base(
    client: AsyncClient,
    name: str,
) -> str:
    response = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": name,
            "description": "",
        },
    )

    assert response.status_code == 201

    return str(response.json()["id"])


@pytest.mark.integration
async def test_rag_query_returns_citations_from_hybrid_retrieval(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    retrieval = FakeHybridRetrievalService()
    app.dependency_overrides[dependencies.get_retrieval_service] = lambda: retrieval
    knowledge_base_id = await create_knowledge_base(
        client,
        "RAG API",
    )

    query_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": knowledge_base_id,
            "query": "refund policy",
            "top_k": 3,
        },
    )

    assert query_response.status_code == 200

    result = query_response.json()

    assert "[S1]" in result["answer"]
    assert result["sources"][0]["label"] == "S1"
    assert result["sources"][0]["document_id"] == str(DOCUMENT_ID)
    assert retrieval.calls == [(uuid.UUID(knowledge_base_id), "refund policy", 3)]


@pytest.mark.integration
async def test_rag_query_returns_empty_result_without_evidence(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    retrieval = FakeHybridRetrievalService()
    app.dependency_overrides[dependencies.get_retrieval_service] = lambda: retrieval
    knowledge_base_id = await create_knowledge_base(
        client,
        "Empty RAG",
    )

    query_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": knowledge_base_id,
            "query": "missing evidence",
        },
    )

    assert query_response.status_code == 200
    assert query_response.json() == {
        "answer": "未找到相关证据。",
        "sources": [],
    }


@pytest.mark.integration
async def test_agent_query_returns_citations_from_agent_service(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    agent = FakeAgentChatService()
    if hasattr(dependencies, "get_agent_chat_service"):
        app.dependency_overrides[dependencies.get_agent_chat_service] = lambda: agent
    knowledge_base_id = await create_knowledge_base(
        client,
        "Agent RAG API",
    )

    query_response = await client.post(
        "/api/v1/rag/agent/query",
        json={
            "knowledge_base_id": knowledge_base_id,
            "query": "refund policy",
        },
    )

    assert query_response.status_code == 200
    result = query_response.json()
    assert result["answer"] == "agent answer"
    assert result["sources"][0]["label"] == "S1"
    assert agent.calls == [(uuid.UUID(knowledge_base_id), "refund policy")]


@pytest.mark.integration
async def test_rag_rejects_missing_knowledge_base_and_invalid_file(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    retrieval = FakeHybridRetrievalService()
    app.dependency_overrides[dependencies.get_retrieval_service] = lambda: retrieval
    missing_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": str(uuid.uuid4()),
            "query": "anything",
        },
    )

    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "knowledge_base_not_found"
    assert retrieval.calls == []

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
