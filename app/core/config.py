from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RAG_AGENT_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "RAG Agent"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    postgres_user: str = "rag_agent"
    postgres_password: str = "rag_agent"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "rag_agent"
    postgres_test_db: str = "rag_agent_test"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "rag-agent"
    minio_secret_key: str = "rag-agent-secret"
    minio_bucket: str = "rag-agent"
    milvus_uri: str = "http://milvus-standalone:19530"
    milvus_token: str | None = None
    milvus_collection: str = "rag_chunks"
    embedding_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("RAG_AGENT_EMBEDDING_BASE_URL", "RAG_AGENT_OPENAI_BASE_URL"),
    )
    embedding_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RAG_AGENT_EMBEDDING_API_KEY", "RAG_AGENT_OPENAI_API_KEY"),
    )
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = ""
    chat_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("RAG_AGENT_CHAT_BASE_URL", "RAG_AGENT_OPENAI_BASE_URL"),
    )
    chat_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RAG_AGENT_CHAT_API_KEY", "RAG_AGENT_OPENAI_API_KEY"),
    )
    chat_model: str = "gpt-4.1-mini"
    agent_max_retrievals: int = 3
    langgraph_strict_msgpack: bool = True
    mineru_base_url: str = "http://mineru:8000"
    paddlex_base_url: str = "http://paddlex:8080"
    default_pdf_parser: Literal["mineru", "paddlex"] = "mineru"
    langfuse_base_url: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_environment: str = "default"

    @property
    def database_url(self) -> URL:
        return self._build_database_url(self.postgres_db)

    @property
    def test_database_url(self) -> URL:
        return self._build_database_url(self.postgres_test_db)

    def _build_database_url(self, database: str) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=database,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
