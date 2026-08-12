from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

import app.main as main_module
from app.main import create_app


def test_http_trace_id_is_returned_and_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fake_setup_checkpointer(database_url: object, *, strict_msgpack: bool) -> None:
        del database_url, strict_msgpack

    monkeypatch.setattr(main_module, "setup_checkpointer", fake_setup_checkpointer, raising=False)

    with caplog.at_level("INFO"), TestClient(create_app()) as client:
        http_client = cast(Any, client)
        response: Response = cast(
            Response,
            http_client.get(
                "/api/v1/health/live",
                headers={"x-trace-id": "trace-test"},
            ),
        )

    assert response.headers["x-trace-id"] == "trace-test"
    assert any(getattr(record, "trace_id", None) == "trace-test" for record in caplog.records)
