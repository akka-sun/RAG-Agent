import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentEvidence
from app.api import dependencies
from app.models import Document
from app.services.agent_chat import AgentAnswer


class FakeAgentChatService:
    def __init__(self, document_id: uuid.UUID) -> None:
        self.document_id = document_id
        self.calls: list[tuple[uuid.UUID, str]] = []

    async def answer(self, *, knowledge_base_id: uuid.UUID, query: str) -> AgentAnswer:
        self.calls.append((knowledge_base_id, query))
        return AgentAnswer(
            content="assistant answer",
            citations=[
                AgentEvidence(
                    label="S1",
                    document_id=self.document_id,
                    filename="policy.md",
                    chunk_id="chunk-1",
                    text="quoted evidence",
                    start=0,
                    end=15,
                    score=0.95,
                )
            ],
        )


async def create_knowledge_base(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": f"SSE KB {uuid.uuid4()}",
            "description": "",
            "embedding_model": "hashing-64",
            "embedding_dimension": 64,
        },
    )

    assert response.status_code == 201
    return str(response.json()["id"])


async def create_conversation(client: AsyncClient, knowledge_base_id: str) -> dict[str, str]:
    response = await client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/conversations",
        json={"title": "Streaming"},
    )

    assert response.status_code == 201
    return response.json()


async def create_document_record(
    db_session: AsyncSession,
    *,
    knowledge_base_id: uuid.UUID,
) -> Document:
    document = Document(
        knowledge_base_id=knowledge_base_id,
        filename="policy.md",
        content_type="text/markdown",
        size_bytes=42,
        source_object_key="source/policy.md",
    )
    db_session.add(document)
    await db_session.commit()
    return document


@pytest.mark.integration
async def test_stream_chat_persists_assistant_message_and_citation(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    knowledge_base_id = await create_knowledge_base(client)
    document = await create_document_record(
        db_session,
        knowledge_base_id=uuid.UUID(knowledge_base_id),
    )
    conversation = await create_conversation(client, knowledge_base_id)
    agent = FakeAgentChatService(document.id)
    app.dependency_overrides[dependencies.get_agent_chat_service] = lambda: agent

    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conversation['id']}/messages/stream",
        json={"content": "Explain retention policy"},
    ) as response:
        body = (await response.aread()).decode()

    assert response.status_code == 200
    assert "event: message_start" in body
    assert "event: token" in body
    assert "event: citation" in body
    assert "event: message_end" in body

    messages = await client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    payload = messages.json()
    assert [message["role"] for message in payload] == ["user", "assistant"]
    assert payload[-1]["content"] == "assistant answer"
    assert payload[-1]["citations"][0]["source_label"] == "S1"
    assert payload[-1]["citations"][0]["document_id"] == str(document.id)
    assert agent.calls == [(uuid.UUID(knowledge_base_id), "Explain retention policy")]
