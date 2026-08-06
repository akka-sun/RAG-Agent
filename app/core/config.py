from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="RAG_AGENT_", extra="ignore"
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
