import os
from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

import app.main as main_module
from app.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_app_uses_configured_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_AGENT_APP_NAME", "测试应用")
    monkeypatch.setenv("RAG_AGENT_DEBUG", "true")

    app = create_app()

    assert app.title == "测试应用"
    assert app.debug is True


def test_live_health_returns_process_status() -> None:
    client = TestClient(create_app())

    response = cast(
        Response,
        client.get("/api/v1/health/live"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_app_sets_up_agent_checkpoint_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, bool]] = []

    async def fake_setup_checkpointer(database_url: object, *, strict_msgpack: bool) -> None:
        calls.append((database_url, strict_msgpack))

    monkeypatch.delenv("LANGGRAPH_STRICT_MSGPACK", raising=False)
    monkeypatch.setattr(
        main_module,
        "setup_checkpointer",
        fake_setup_checkpointer,
        raising=False,
    )

    with TestClient(main_module.create_app()) as client:
        response = cast(
            Response,
            client.get("/api/v1/health/live"),  # pyright: ignore[reportUnknownMemberType]
        )

    assert response.status_code == 200
    assert os.environ["LANGGRAPH_STRICT_MSGPACK"] == "true"
    assert calls == [(get_settings().database_url, True)]
