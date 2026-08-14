import uuid

import pytest
from httpx import AsyncClient


async def create_knowledge_base(client: AsyncClient, name: str) -> str:
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
async def test_create_list_get_messages_and_delete_conversation(
    client: AsyncClient,
) -> None:
    knowledge_base_id = await create_knowledge_base(client, "Conversation API")

    created = await client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/conversations",
        json={"title": "  Research  "},
    )

    assert created.status_code == 201
    conversation = created.json()
    assert conversation["title"] == "Research"
    assert conversation["knowledge_base_id"] == knowledge_base_id

    listed = await client.get(f"/api/v1/knowledge-bases/{knowledge_base_id}/conversations")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == conversation["id"]

    fetched = await client.get(f"/api/v1/conversations/{conversation['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Research"

    messages = await client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assert messages.json() == []

    deleted = await client.delete(f"/api/v1/conversations/{conversation['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/conversations/{conversation['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "conversation_not_found"


@pytest.mark.integration
async def test_conversation_create_rejects_missing_knowledge_base(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/conversations",
        json={"title": "Research"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "knowledge_base_not_found"
