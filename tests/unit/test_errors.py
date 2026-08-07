from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.errors import register_error_handlers
from app.core.exceptions import DocumentNotFoundError
from app.services.knowledge_base import KnowledgeBaseNotFoundError


def test_not_found_error_uses_unified_response() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise KnowledgeBaseNotFoundError

    client = TestClient(app)
    response = cast(
        Response,
        client.get("/boom"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "knowledge_base_not_found",
            "message": "知识库不存在",
            "details": None,
        }
    }


def test_unhandled_error_hides_internal_details() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise RuntimeError("database password must not leak")

    client = TestClient(app, raise_server_exceptions=False)
    response = cast(
        Response,
        client.get("/boom"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "服务器内部错误",
            "details": None,
        }
    }


def test_document_error_uses_unified_handler() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise DocumentNotFoundError("missing")

    response = cast(
        Response,
        TestClient(app).get("/boom"),  # pyright: ignore[reportUnknownMemberType]
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
