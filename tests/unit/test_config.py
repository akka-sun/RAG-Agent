from pathlib import Path

import pytest

from app.config import Settings


def test_settings_read_environment_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAG_AGENT_APP_NAME", "测试 RAG")
    monkeypatch.setenv("RAG_AGENT_APP_ENV", "test")
    monkeypatch.setenv("RAG_AGENT_DEBUG", "true")
    monkeypatch.setenv("RAG_AGENT_API_V1_PREFIX", "/custom-api")

    settings = Settings()

    assert settings.app_name == "测试 RAG"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.api_v1_prefix == "/custom-api"
