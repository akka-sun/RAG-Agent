import os

import pytest

from app.agent.checkpoint import ensure_langgraph_security_env


def test_checkpointer_sets_strict_msgpack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGGRAPH_STRICT_MSGPACK", raising=False)

    ensure_langgraph_security_env()

    assert os.environ["LANGGRAPH_STRICT_MSGPACK"] == "true"
