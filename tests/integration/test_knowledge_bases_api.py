import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_knowledge_base_crud(
    client: AsyncClient,
) -> None:
    create_response = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "产品文档",
            "description": "产品知识",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
        },
    )

    assert create_response.status_code == 201
    item = create_response.json()

    list_response = await client.get("/api/v1/knowledge-bases")
    assert list_response.status_code == 200
    assert list_response.json() == [item]

    detail_response = await client.get(f"/api/v1/knowledge-bases/{item['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json() == item

    delete_response = await client.delete(f"/api/v1/knowledge-bases/{item['id']}")
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/api/v1/knowledge-bases/{item['id']}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "knowledge_base_not_found"


@pytest.mark.integration
async def test_duplicate_name_returns_conflict(
    client: AsyncClient,
) -> None:
    payload = {
        "name": "重复名称",
        "description": "",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 1536,
    }

    first_response = await client.post(
        "/api/v1/knowledge-bases",
        json=payload,
    )
    assert first_response.status_code == 201

    duplicate_response = await client.post(
        "/api/v1/knowledge-bases",
        json=payload,
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "knowledge_base_name_conflict"


@pytest.mark.integration
async def test_invalid_dimension_returns_unified_validation_error(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "无效维度",
            "description": "",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 0,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
