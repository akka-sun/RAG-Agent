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


def test_stage5_agent_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RAG_AGENT_CHAT_BASE_URL", raising=False)
    monkeypatch.delenv("RAG_AGENT_CHAT_API_KEY", raising=False)
    monkeypatch.setenv("RAG_AGENT_OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("RAG_AGENT_OPENAI_API_KEY", "key")
    monkeypatch.setenv("RAG_AGENT_CHAT_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("RAG_AGENT_AGENT_MAX_RETRIEVALS", "3")

    settings = Settings()

    assert settings.chat_base_url == "https://api.example.test/v1"
    assert settings.chat_api_key == "key"
    assert settings.chat_model == "gpt-4.1-mini"
    assert settings.agent_max_retrievals == 3
    assert settings.langgraph_strict_msgpack is True


def test_stage7_parser_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAG_AGENT_MINERU_BASE_URL", "http://mineru:8000")
    monkeypatch.setenv("RAG_AGENT_PADDLEX_BASE_URL", "http://paddlex:8080")
    monkeypatch.setenv("RAG_AGENT_DEFAULT_PDF_PARSER", "mineru")

    settings = Settings()

    assert settings.mineru_base_url == "http://mineru:8000"
    assert settings.paddlex_base_url == "http://paddlex:8080"
    assert settings.default_pdf_parser == "mineru"


def test_stage8_langfuse_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAG_AGENT_LANGFUSE_BASE_URL", "https://langfuse.example.test")
    monkeypatch.setenv("RAG_AGENT_LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("RAG_AGENT_LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("RAG_AGENT_LANGFUSE_ENVIRONMENT", "staging")

    settings = Settings()

    assert settings.langfuse_base_url == "https://langfuse.example.test"
    assert settings.langfuse_public_key == "pk-test"
    assert settings.langfuse_secret_key == "sk-test"
    assert settings.langfuse_environment == "staging"
