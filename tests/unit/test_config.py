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


def test_settings_build_async_database_urls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAG_AGENT_POSTGRES_USER", "rag_user")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_PASSWORD", "p@ss/word")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_HOST", "postgres")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_PORT", "5432")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_DB", "rag_agent")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_TEST_DB", "rag_agent_test")

    settings = Settings()

    assert settings.database_url.drivername == "postgresql+asyncpg"
    assert settings.database_url.database == "rag_agent"
    assert settings.test_database_url.database == "rag_agent_test"
    assert settings.database_url.password == "p@ss/word"


def test_stage4_external_service_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAG_AGENT_MILVUS_URI", "http://milvus:19530")
    monkeypatch.setenv("RAG_AGENT_MILVUS_COLLECTION", "rag_chunks")
    monkeypatch.setenv("RAG_AGENT_OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("RAG_AGENT_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("RAG_AGENT_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("RAG_AGENT_EMBEDDING_DIMENSION", "1536")
    monkeypatch.setenv("RAG_AGENT_RERANK_BASE_URL", "https://rerank.example.test")
    monkeypatch.setenv("RAG_AGENT_RERANK_API_KEY", "rerank-key")
    monkeypatch.setenv("RAG_AGENT_RERANK_MODEL", "bge-reranker-v2")

    settings = Settings()

    assert settings.milvus_uri == "http://milvus:19530"
    assert settings.embedding_dimension == 1536
    assert settings.rerank_model == "bge-reranker-v2"
