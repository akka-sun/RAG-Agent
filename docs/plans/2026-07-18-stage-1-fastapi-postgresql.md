# 阶段 1：FastAPI 与 PostgreSQL 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立从 FastAPI 请求到 PostgreSQL 事务提交的完整链路，实现知识库创建、列表、详情和删除，并通过迁移、单元测试和真实数据库集成测试验收。

**Architecture:** API 层只解析请求、注入依赖和装配响应；Service 层拥有业务规则与事务边界；Repository 层封装 SQLAlchemy 2.x 异步查询。PostgreSQL 表结构只由 Alembic 迁移建立，应用启动不调用 `create_all()`。

**Tech Stack:** Python 3.12、FastAPI、Pydantic Settings、SQLAlchemy 2.0 async、asyncpg、Alembic、PostgreSQL 18、pytest、pytest-asyncio、Ruff、Pyright、Docker Compose。

## Global Constraints

- 项目目录固定为 `RAG-Agent/`，不得导入其他项目的业务代码。
- Python 版本范围保持 `>=3.12,<3.14`。
- PostgreSQL 使用 `postgres:18-alpine`，仅绑定宿主机 `127.0.0.1`。
- 应用数据库与测试数据库隔离，分别为 `rag_agent` 和 `rag_agent_test`。
- 所有开发、迁移、测试和检查命令在 Docker Compose 容器中运行。
- 代码标识符使用英文；文档、注释和 API 描述使用中文。
- 每个功能先观察目标测试失败，再编写最小实现。
- 路由不得直接执行 ORM 查询；Repository 不得自行提交事务；事务由 Service 用例控制。
- 不增加 documents、Redis、ARQ、MinIO、Milvus、认证、分页、更新接口或通用 Repository 基类。
- 数据库结构只由 Alembic 迁移创建，应用启动时不得调用 `Base.metadata.create_all()`。

---

## 文件结构

阶段结束时新增或修改：

```text
RAG-Agent/
├── alembic/
│   ├── versions/
│   │   └── 20260718_0001_create_knowledge_bases.py
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   ├── errors.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── knowledge_bases.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── knowledge_base.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── knowledge_base.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── errors.py
│   │   └── knowledge_base.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── knowledge_base.py
│   ├── config.py
│   ├── db.py
│   └── main.py
├── docker/postgres/init-test-db.sql
├── tests/
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_migrations.py
│   │   ├── test_knowledge_base_repository.py
│   │   └── test_knowledge_bases_api.py
│   └── unit/
│       ├── test_config.py
│       ├── test_errors.py
│       └── test_knowledge_base_service.py
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

### Task 1: PostgreSQL 服务与强类型数据库配置

**Files:**

- Modify: `pyproject.toml`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `docker/postgres/init-test-db.sql`
- Modify: `app/config.py`
- Modify: `tests/unit/test_config.py`

**Interfaces:**

- Consumes: 现有 `Settings` 与 `get_settings() -> Settings`。
- Produces: `Settings.database_url -> URL`、`Settings.test_database_url -> URL`，以及 healthy 的 `postgres` Compose 服务。

- [ ] **Step 1: 在配置测试中写数据库 URL 失败测试**

在 `tests/unit/test_config.py` 追加：

```python
def test_settings_build_async_database_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_AGENT_POSTGRES_USER", "rag_user")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_PASSWORD", "p@ss/word")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_HOST", "postgres")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_PORT", "5432")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_DB", "rag_agent")
    monkeypatch.setenv("RAG_AGENT_POSTGRES_TEST_DB", "rag_agent_test")

    settings = Settings(_env_file=None)

    assert settings.database_url.drivername == "postgresql+asyncpg"
    assert settings.database_url.database == "rag_agent"
    assert settings.test_database_url.database == "rag_agent_test"
    assert settings.database_url.password == "p@ss/word"
```

- [ ] **Step 2: 运行测试并确认因字段缺失失败**

Run:

```powershell
docker compose run --rm api uv run --no-sync pytest tests/unit/test_config.py -v
```

Expected: FAIL，错误包含 `Settings` 没有 `database_url`。

- [ ] **Step 3: 增加依赖**

将 `pyproject.toml` 的运行依赖补充为：

```toml
dependencies = [
    "alembic>=1.18.5",
    "asyncpg>=0.30",
    "fastapi>=0.121",
    "pydantic-settings>=2.10",
    "sqlalchemy[asyncio]>=2.0.51",
    "uvicorn[standard]>=0.34.2",
]
```

将测试依赖补充为：

```toml
test = [
    "httpx>=0.28",
    "pytest>=8.0",
    "pytest-asyncio>=1.0",
]
```

- [ ] **Step 4: 实现数据库配置**

在 `app/config.py` 导入：

```python
from sqlalchemy import URL
```

在 `Settings` 中增加：

```python
postgres_user: str = "rag_agent"
postgres_password: str = "rag_agent"
postgres_host: str = "postgres"
postgres_port: int = 5432
postgres_db: str = "rag_agent"
postgres_test_db: str = "rag_agent_test"


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
```

- [ ] **Step 5: 增加 PostgreSQL 与测试数据库初始化**

创建 `docker/postgres/init-test-db.sql`：

```sql
CREATE DATABASE rag_agent_test;
```

在 `docker-compose.yml` 的 `services` 下增加：

```yaml
  postgres:
    image: postgres:18-alpine
    container_name: rag-agent-postgres-dev
    environment:
      POSTGRES_USER: rag_agent
      POSTGRES_PASSWORD: rag_agent
      POSTGRES_DB: rag_agent
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
      - ./docker/postgres/init-test-db.sql:/docker-entrypoint-initdb.d/10-init-test-db.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag_agent -d rag_agent"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s
```

在 `api` 服务增加：

```yaml
    depends_on:
      postgres:
        condition: service_healthy
```

文件末尾增加：

```yaml
volumes:
  postgres_data:
```

- [ ] **Step 6: 更新环境变量示例**

在 `.env.example` 追加：

```dotenv
RAG_AGENT_POSTGRES_USER=rag_agent
RAG_AGENT_POSTGRES_PASSWORD=rag_agent
RAG_AGENT_POSTGRES_HOST=postgres
RAG_AGENT_POSTGRES_PORT=5432
RAG_AGENT_POSTGRES_DB=rag_agent
RAG_AGENT_POSTGRES_TEST_DB=rag_agent_test
```

- [ ] **Step 7: 重建镜像并验证配置与 PostgreSQL**

Run:

```powershell
docker compose up -d --build postgres api
docker compose ps
docker compose exec api uv run --no-sync pytest tests/unit/test_config.py -v
```

Expected: `postgres` 与 `api` 均为 healthy；配置测试全部通过。

- [ ] **Step 8: 提交**

```powershell
git add pyproject.toml docker-compose.yml .env.example docker/postgres/init-test-db.sql app/config.py tests/unit/test_config.py
git commit -m "feat: 增加 PostgreSQL 开发环境与配置"
```

---

### Task 2: 异步数据库会话与 ORM 基础

**Files:**

- Create: `app/db.py`
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `tests/unit/test_db.py`

**Interfaces:**

- Consumes: `get_settings().database_url`。
- Produces: `engine: AsyncEngine`、`async_session_factory: async_sessionmaker[AsyncSession]`、`get_session() -> AsyncIterator[AsyncSession]`、`Base(DeclarativeBase)`。

- [ ] **Step 1: 编写会话依赖失败测试**

创建 `tests/unit/test_db.py`：

```python
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session


@pytest.mark.asyncio
async def test_get_session_yields_async_session() -> None:
    session_iterator: AsyncIterator[AsyncSession] = get_session()

    session = await anext(session_iterator)

    assert isinstance(session, AsyncSession)
    await session_iterator.aclose()
```

- [ ] **Step 2: 运行测试并确认模块缺失**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_db.py -v
```

Expected: collection ERROR，包含 `No module named 'app.db'`。

- [ ] **Step 3: 创建 ORM Base**

创建 `app/models/__init__.py` 空文件，并创建 `app/models/base.py`：

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

- [ ] **Step 4: 创建异步 Engine 和会话依赖**

创建 `app/db.py`：

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 5: 运行测试和类型检查**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_db.py -v
docker compose exec api uv run --no-sync pyright
```

Expected: 测试通过；Pyright 为 0 errors。

- [ ] **Step 6: 提交**

```powershell
git add app/db.py app/models/__init__.py app/models/base.py tests/unit/test_db.py
git commit -m "feat: 增加异步数据库会话"
```

---

### Task 3: KnowledgeBase 模型与 Alembic 首个迁移

**Files:**

- Create: `app/models/knowledge_base.py`
- Modify: `app/models/__init__.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/20260718_0001_create_knowledge_bases.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_migrations.py`

**Interfaces:**

- Consumes: `Base.metadata` 与 `Settings.test_database_url`。
- Produces: `KnowledgeBase` ORM 类和可从空库升级的 Alembic revision `20260718_0001`。

- [ ] **Step 1: 初始化 Alembic async 模板**

```powershell
docker compose exec api uv run --no-sync alembic init -t async alembic
```

Expected: 创建 `alembic/` 和 `alembic.ini`。不要生成 revision。

- [ ] **Step 2: 编写空库迁移失败测试**

创建 `tests/integration/__init__.py` 空文件，并创建 `tests/integration/test_migrations.py`：

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def test_migration_creates_knowledge_bases_table() -> None:
    engine = create_async_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'knowledge_bases'"
                    ")"
                )
            )
            assert result.scalar_one() is True
    finally:
        await engine.dispose()
```

在 `pyproject.toml` 的 pytest 配置增加：

```toml
asyncio_mode = "auto"
```

- [ ] **Step 3: 清空测试库并观察迁移测试失败**

```powershell
docker compose exec postgres psql -U rag_agent -d rag_agent_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec api uv run --no-sync pytest tests/integration/test_migrations.py -v
```

Expected: FAIL，`assert False is True`。

- [ ] **Step 4: 实现 KnowledgeBase ORM 模型**

创建 `app/models/knowledge_base.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint(
            "embedding_dimension > 0",
            name="embedding_dimension_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

更新 `app/models/__init__.py`：

```python
from app.models.knowledge_base import KnowledgeBase

__all__ = ["KnowledgeBase"]
```

- [ ] **Step 5: 配置 Alembic 使用应用配置和元数据**

在 `alembic/env.py` 中保留 async 模板结构，加入：

```python
from app.config import get_settings
from app.models import KnowledgeBase  # noqa: F401
from app.models.base import Base

config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.render_as_string(hide_password=False),
)
target_metadata = Base.metadata
```

删除模板原有的 `target_metadata = None`。在 `alembic.ini` 中将 `sqlalchemy.url` 保留为空占位：

```ini
sqlalchemy.url =
```

- [ ] **Step 6: 创建确定性的首个迁移**

创建 `alembic/versions/20260718_0001_create_knowledge_bases.py`：

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "embedding_dimension > 0",
            name=op.f("ck_knowledge_bases_embedding_dimension_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_bases")),
        sa.UniqueConstraint("name", name=op.f("uq_knowledge_bases_name")),
    )


def downgrade() -> None:
    op.drop_table("knowledge_bases")
```

- [ ] **Step 7: 从空测试库执行迁移并验证**

```powershell
docker compose exec postgres psql -U rag_agent -d rag_agent_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -e RAG_AGENT_POSTGRES_DB=rag_agent_test api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync pytest tests/integration/test_migrations.py -v
docker compose exec -e RAG_AGENT_POSTGRES_DB=rag_agent_test api uv run --no-sync alembic current --check-heads
```

Expected: migration test PASS；`alembic current --check-heads` 显示 `20260718_0001 (head)`。

- [ ] **Step 8: 提交**

```powershell
git add alembic.ini alembic app/models pyproject.toml tests/integration
git commit -m "feat: 增加知识库模型与数据库迁移"
```

---

### Task 4: 知识库 Schema、业务异常与统一错误结构

**Files:**

- Create: `app/schemas/__init__.py`
- Create: `app/schemas/errors.py`
- Create: `app/schemas/knowledge_base.py`
- Create: `app/services/__init__.py`
- Create: `app/services/knowledge_base.py`
- Create: `app/api/__init__.py`
- Create: `app/api/errors.py`
- Create: `tests/unit/test_errors.py`

**Interfaces:**

- Produces: `KnowledgeBaseCreate`、`KnowledgeBaseResponse`、`KnowledgeBaseNotFoundError`、`KnowledgeBaseNameConflictError`、统一 `ErrorResponse` 和异常处理器注册函数 `register_error_handlers(app: FastAPI) -> None`。

- [ ] **Step 1: 编写业务异常响应失败测试**

创建 `tests/unit/test_errors.py`：

```python
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.errors import register_error_handlers
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
```

- [ ] **Step 2: 运行测试并确认模块缺失**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_errors.py -v
```

Expected: collection ERROR，缺少 `app.api.errors`。

- [ ] **Step 3: 创建知识库请求与响应 Schema**

创建空的 `app/schemas/__init__.py`，并创建 `app/schemas/knowledge_base.py`：

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    embedding_model: str = Field(min_length=1, max_length=200)
    embedding_dimension: int = Field(gt=0)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    embedding_model: str
    embedding_dimension: int
    created_at: datetime
    updated_at: datetime
```

创建 `app/schemas/errors.py`：

```python
import logging
from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
```

- [ ] **Step 4: 定义业务异常**

创建 `app/services/__init__.py` 空文件，并创建 `app/services/knowledge_base.py` 的初始内容：

```python
class KnowledgeBaseError(Exception):
    pass


class KnowledgeBaseNotFoundError(KnowledgeBaseError):
    pass


class KnowledgeBaseNameConflictError(KnowledgeBaseError):
    pass
```

- [ ] **Step 5: 实现统一错误处理器**

创建 `app/api/__init__.py` 空文件，并创建 `app/api/errors.py`：

```python
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.services.knowledge_base import (
    KnowledgeBaseNameConflictError,
    KnowledgeBaseNotFoundError,
)

logger = logging.getLogger(__name__)


def error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(KnowledgeBaseNotFoundError)
    async def handle_not_found(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: KnowledgeBaseNotFoundError
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=404,
            content=error_body("knowledge_base_not_found", "知识库不存在"),
        )

    @app.exception_handler(KnowledgeBaseNameConflictError)
    async def handle_conflict(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: KnowledgeBaseNameConflictError
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=409,
            content=error_body("knowledge_base_name_conflict", "知识库名称已存在"),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                error_body("validation_error", "请求参数校验失败", exc.errors())
            ),
        )

    @app.exception_handler(Exception)
    async def handle_internal_error(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: Exception
    ) -> JSONResponse:
        del request
        logger.error("未处理的 API 异常", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "服务器内部错误"),
        )
```

- [ ] **Step 6: 运行测试和静态检查**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_errors.py -v
docker compose exec api uv run --no-sync ruff check app tests
docker compose exec api uv run --no-sync pyright
```

Expected: 测试通过；Ruff 和 Pyright 通过。只在 `TestClient.get()` 这一处第三方类型缺口使用定向忽略，不关闭严格类型检查。

- [ ] **Step 7: 提交**

```powershell
git add app/api app/schemas app/services tests/unit/test_errors.py
git commit -m "feat: 增加知识库契约与统一错误响应"
```

---

### Task 5: KnowledgeBase Repository 与真实数据库集成测试

**Files:**

- Create: `app/repositories/__init__.py`
- Create: `app/repositories/knowledge_base.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_knowledge_base_repository.py`

**Interfaces:**

- Produces: `KnowledgeBaseRepository(session)`，方法 `add`、`get_by_id`、`list_all`、`delete`。
- Repository 只执行 `add/flush/refresh/select/delete`，不调用 `commit()`。

- [ ] **Step 1: 创建真实测试 Session fixture**

创建 `tests/integration/conftest.py`：

```python
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


test_engine = create_async_engine(get_settings().test_database_url)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with test_session_factory() as session:
        await session.execute(text("TRUNCATE TABLE knowledge_bases"))
        await session.commit()
        yield session
        await session.rollback()
        await session.execute(text("TRUNCATE TABLE knowledge_bases"))
        await session.commit()
```

- [ ] **Step 2: 编写 Repository 失败测试**

创建 `tests/integration/test_knowledge_base_repository.py`：

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import KnowledgeBaseRepository


async def test_repository_add_list_get_and_delete(db_session: AsyncSession) -> None:
    repository = KnowledgeBaseRepository(db_session)
    item = KnowledgeBase(
        name="产品文档",
        description="产品知识",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
    )

    await repository.add(item)
    await db_session.commit()

    assert await repository.get_by_id(item.id) is item
    assert [row.name for row in await repository.list_all()] == ["产品文档"]

    await repository.delete(item)
    await db_session.commit()

    assert await repository.get_by_id(item.id) is None
    assert await repository.get_by_id(uuid.uuid4()) is None
```

- [ ] **Step 3: 运行测试并确认 Repository 模块缺失**

```powershell
docker compose exec api uv run --no-sync pytest tests/integration/test_knowledge_base_repository.py -v
```

Expected: collection ERROR，缺少 `app.repositories.knowledge_base`。

- [ ] **Step 4: 实现 Repository**

创建 `app/repositories/__init__.py` 空文件，并创建 `app/repositories/knowledge_base.py`：

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: KnowledgeBase) -> KnowledgeBase:
        self._session.add(item)
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None:
        return await self._session.get(KnowledgeBase, item_id)

    async def list_all(self) -> list[KnowledgeBase]:
        statement = select(KnowledgeBase).order_by(
            KnowledgeBase.created_at.asc(), KnowledgeBase.id.asc()
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def delete(self, item: KnowledgeBase) -> None:
        await self._session.delete(item)
        await self._session.flush()
```

- [ ] **Step 5: 运行集成测试与类型检查**

```powershell
docker compose exec api uv run --no-sync pytest tests/integration/test_knowledge_base_repository.py -v
docker compose exec api uv run --no-sync pyright
```

Expected: Repository 测试通过；Pyright 0 errors。

- [ ] **Step 6: 提交**

```powershell
git add app/repositories tests/integration/conftest.py tests/integration/test_knowledge_base_repository.py
git commit -m "feat: 增加知识库数据访问层"
```

---

### Task 6: KnowledgeBase Service 与事务边界

**Files:**

- Modify: `app/services/knowledge_base.py`
- Create: `tests/unit/test_knowledge_base_service.py`

**Interfaces:**

- Produces: `KnowledgeBaseRepositoryProtocol` 与 `KnowledgeBaseService` 的 `create`、`list_all`、`get`、`delete`。
- Service 调用 `AsyncSession.commit/rollback`，Repository 不提交。

- [ ] **Step 1: 编写 Service 单元测试**

创建 `tests/unit/test_knowledge_base_service.py`，使用最小内存替身：

```python
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.knowledge_base import KnowledgeBaseNotFoundError, KnowledgeBaseService


class FakeRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, KnowledgeBase] = {}

    async def add(self, item: KnowledgeBase) -> KnowledgeBase:
        self.items[item.id] = item
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None:
        return self.items.get(item_id)

    async def list_all(self) -> list[KnowledgeBase]:
        return list(self.items.values())

    async def delete(self, item: KnowledgeBase) -> None:
        del self.items[item.id]


@pytest.mark.asyncio
async def test_service_create_and_commit() -> None:
    session = AsyncMock(spec=AsyncSession)
    service = KnowledgeBaseService(FakeRepository(), session)

    item = await service.create(
        KnowledgeBaseCreate(
            name="产品文档",
            description="",
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
        )
    )

    assert item.name == "产品文档"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_get_missing_raises_not_found() -> None:
    session = AsyncMock(spec=AsyncSession)
    service = KnowledgeBaseService(FakeRepository(), session)

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.get(uuid.uuid4())
```

- [ ] **Step 2: 运行测试并确认 Service 缺少行为**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_knowledge_base_service.py -v
```

Expected: collection ERROR 或 FAIL，`KnowledgeBaseService` 尚未定义。

- [ ] **Step 3: 实现协议和 Service**

将 `app/services/knowledge_base.py` 扩展为：

```python
import uuid
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate


class KnowledgeBaseError(Exception):
    pass


class KnowledgeBaseNotFoundError(KnowledgeBaseError):
    pass


class KnowledgeBaseNameConflictError(KnowledgeBaseError):
    pass


class KnowledgeBaseRepositoryProtocol(Protocol):
    async def add(self, item: KnowledgeBase) -> KnowledgeBase: ...
    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None: ...
    async def list_all(self) -> list[KnowledgeBase]: ...
    async def delete(self, item: KnowledgeBase) -> None: ...


class KnowledgeBaseService:
    def __init__(
        self,
        repository: KnowledgeBaseRepositoryProtocol,
        session: AsyncSession,
    ) -> None:
        self._repository = repository
        self._session = session

    async def create(self, data: KnowledgeBaseCreate) -> KnowledgeBase:
        item = KnowledgeBase(**data.model_dump())
        try:
            await self._repository.add(item)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise KnowledgeBaseNameConflictError from exc
        return item

    async def list_all(self) -> list[KnowledgeBase]:
        return await self._repository.list_all()

    async def get(self, item_id: uuid.UUID) -> KnowledgeBase:
        item = await self._repository.get_by_id(item_id)
        if item is None:
            raise KnowledgeBaseNotFoundError
        return item

    async def delete(self, item_id: uuid.UUID) -> None:
        item = await self.get(item_id)
        await self._repository.delete(item)
        await self._session.commit()
```

- [ ] **Step 4: 增加删除和列表测试**

在单元测试追加：

```python
@pytest.mark.asyncio
async def test_service_list_and_delete() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = FakeRepository()
    service = KnowledgeBaseService(repository, session)
    item = KnowledgeBase(
        name="产品文档",
        description="",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
    )
    await repository.add(item)

    assert await service.list_all() == [item]

    await service.delete(item.id)

    assert repository.items == {}
    session.commit.assert_awaited_once()
```

- [ ] **Step 5: 运行单元测试和检查**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_knowledge_base_service.py -v
docker compose exec api uv run --no-sync ruff check app tests
docker compose exec api uv run --no-sync pyright
```

Expected: Service 测试全部通过；Ruff/Pyright 通过。

- [ ] **Step 6: 提交**

```powershell
git add app/services/knowledge_base.py tests/unit/test_knowledge_base_service.py
git commit -m "feat: 增加知识库业务服务"
```

---

### Task 7: 知识库 CRUD 路由与依赖注入

**Files:**

- Create: `app/api/dependencies.py`
- Create: `app/api/routes/__init__.py`
- Create: `app/api/routes/knowledge_bases.py`
- Modify: `app/main.py`
- Create: `tests/integration/test_knowledge_bases_api.py`

**Interfaces:**

- Produces: `POST/GET/DELETE /api/v1/knowledge-bases` API。
- Consumes: `get_session`、`KnowledgeBaseRepository`、`KnowledgeBaseService`、统一错误处理器。

- [ ] **Step 1: 编写真实 API 失败测试**

创建 `tests/integration/test_knowledge_bases_api.py`：

```python
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.main import create_app


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_knowledge_base_crud(client: AsyncClient) -> None:
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

    assert (await client.get("/api/v1/knowledge-bases")).json() == [item]
    assert (await client.get(f"/api/v1/knowledge-bases/{item['id']}")).json() == item
    assert (await client.delete(f"/api/v1/knowledge-bases/{item['id']}")).status_code == 204

    missing = await client.get(f"/api/v1/knowledge-bases/{item['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "knowledge_base_not_found"
```

- [ ] **Step 2: 运行测试并确认路由返回 404**

```powershell
docker compose exec api uv run --no-sync pytest tests/integration/test_knowledge_bases_api.py -v
```

Expected: FAIL，创建接口返回 404。

- [ ] **Step 3: 创建依赖装配**

创建 `app/api/dependencies.py`：

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.knowledge_base import KnowledgeBaseService

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_knowledge_base_service(session: SessionDependency) -> KnowledgeBaseService:
    return KnowledgeBaseService(KnowledgeBaseRepository(session), session)


KnowledgeBaseServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]
```

- [ ] **Step 4: 创建 CRUD 路由**

创建 `app/api/routes/__init__.py` 空文件，并创建 `app/api/routes/knowledge_bases.py`：

```python
import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import KnowledgeBaseServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse


router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    service: KnowledgeBaseServiceDependency,
) -> KnowledgeBaseResponse:
    item = await service.create(data)
    return KnowledgeBaseResponse.model_validate(item)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    service: KnowledgeBaseServiceDependency,
) -> list[KnowledgeBaseResponse]:
    items = await service.list_all()
    return [KnowledgeBaseResponse.model_validate(item) for item in items]


@router.get(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def get_knowledge_base(
    knowledge_base_id: uuid.UUID,
    service: KnowledgeBaseServiceDependency,
) -> KnowledgeBaseResponse:
    item = await service.get(knowledge_base_id)
    return KnowledgeBaseResponse.model_validate(item)


@router.delete(
    "/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def delete_knowledge_base(
    knowledge_base_id: uuid.UUID,
    service: KnowledgeBaseServiceDependency,
) -> Response:
    await service.delete(knowledge_base_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: 在应用工厂注册路由与错误处理器**

在 `app/main.py` 导入：

```python
from app.api.errors import register_error_handlers
from app.api.routes.knowledge_bases import router as knowledge_bases_router
```

在 `create_app()` 中、`return application` 前增加：

```python
    router.include_router(knowledge_bases_router)
    application.include_router(router)
    register_error_handlers(application)
```

确保原有的 `application.include_router(router)` 只保留一次。

- [ ] **Step 6: 运行 CRUD 集成测试**

```powershell
docker compose exec api uv run --no-sync pytest tests/integration/test_knowledge_bases_api.py -v
```

Expected: CRUD 测试通过。

- [ ] **Step 7: 增加名称冲突与校验错误测试**

在同一测试文件追加：

```python
async def test_duplicate_name_returns_conflict(client: AsyncClient) -> None:
    payload = {
        "name": "重复名称",
        "description": "",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 1536,
    }
    assert (await client.post("/api/v1/knowledge-bases", json=payload)).status_code == 201

    response = await client.post("/api/v1/knowledge-bases", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "knowledge_base_name_conflict"


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
```

- [ ] **Step 8: 运行全部测试和静态检查**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit tests/integration -v
docker compose exec api uv run --no-sync ruff format --check app tests
docker compose exec api uv run --no-sync ruff check app tests
docker compose exec api uv run --no-sync pyright
```

Expected: 全部通过，Pyright 为 0 errors。

- [ ] **Step 9: 提交**

```powershell
git add app/api app/main.py tests/integration/test_knowledge_bases_api.py
git commit -m "feat: 增加知识库 CRUD API"
```

---

### Task 8: 阶段 1 集成验收与学习文档

**Files:**

- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`

**Interfaces:**

- Consumes: Task 1～7 的 PostgreSQL、迁移、CRUD 和测试命令。
- Produces: 可从空环境复现的阶段 1 文档和真实验收记录。

- [ ] **Step 1: 验证空测试库迁移**

```powershell
docker compose exec postgres psql -U rag_agent -d rag_agent_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -e RAG_AGENT_POSTGRES_DB=rag_agent_test api uv run --no-sync alembic upgrade head
docker compose exec -e RAG_AGENT_POSTGRES_DB=rag_agent_test api uv run --no-sync alembic current --check-heads
```

Expected: 数据库位于唯一的 head revision。

- [ ] **Step 2: 运行完整质量门槛**

```powershell
docker compose exec api uv run --no-sync ruff format --check app tests
docker compose exec api uv run --no-sync ruff check app tests
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
```

Expected: format、lint、类型、单元和集成测试全部通过。

- [ ] **Step 3: 使用真实 HTTP 完成 CRUD**

```powershell
$body = @{
  name = "阶段一验收知识库"
  description = "真实 HTTP 验收"
  embedding_model = "text-embedding-3-small"
  embedding_dimension = 1536
} | ConvertTo-Json

$created = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/knowledge-bases -ContentType application/json -Body $body
Invoke-RestMethod http://127.0.0.1:8000/api/v1/knowledge-bases
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/knowledge-bases/$($created.id)"
Invoke-RestMethod -Method Delete "http://127.0.0.1:8000/api/v1/knowledge-bases/$($created.id)"
```

Expected: POST 为 201，列表和详情包含同一 ID，DELETE 为 204。

- [ ] **Step 4: 更新 README**

在 `README.md` 增加：

````markdown
## 数据库迁移

```powershell
docker compose up -d --build postgres api
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync alembic current --check-heads
```

## 阶段 1 API

- `POST /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases/{knowledge_base_id}`
- `DELETE /api/v1/knowledge-bases/{knowledge_base_id}`
````

- [ ] **Step 5: 完成口述验收**

不看文档回答：

1. 一个创建请求从路由到事务提交经过哪些对象？
2. 为什么路由不直接写 SQLAlchemy 查询？
3. `flush`、`commit`、`rollback` 和 `refresh` 分别做什么？
4. 为什么 Repository 不调用 `commit()`？
5. Engine、连接池、Connection 和 Session 的关系是什么？
6. 为什么“先查询名称是否存在”不能代替数据库唯一约束？
7. Alembic 为什么不能被应用启动时的 `create_all()` 替代？
8. 单元测试和真实 PostgreSQL 集成测试分别发现什么问题？

- [ ] **Step 6: 更新学习进度**

在 `docs/learning-roadmap.md` 进度表追加真实记录，格式：

```markdown
| 2026-07-18 | 阶段 1 | PostgreSQL、异步 ORM、Alembic、知识库 CRUD、统一错误响应 | 空库迁移、单元测试、集成测试、Ruff、Pyright、真实 HTTP CRUD | 事务边界、迁移与 Repository/Service 职责 | 连接池、并发唯一约束与 Alembic 回滚 |
```

若实际完成日期不是 2026-07-18，提交前将日期改为真实完成日期；最后一列必须替换为代码审查和口述验收中真实暴露的待复习项。

- [ ] **Step 7: 提交阶段文档**

```powershell
git add README.md docs/learning-roadmap.md
git commit -m "docs: 完善阶段一数据库使用与学习记录"
```

## 阶段 1 完成定义

- [ ] `postgres` 与 `api` 容器均为 healthy。
- [ ] 空的 `rag_agent_test` 数据库可通过 `alembic upgrade head` 建表。
- [ ] 创建、列表、详情和删除知识库 API 契约通过。
- [ ] 名称冲突返回统一 409，资源不存在返回统一 404，请求无效返回统一 422。
- [ ] 路由不直接执行 ORM 查询，Repository 不提交事务，Service 拥有事务边界。
- [ ] 单元测试不访问 PostgreSQL，集成测试访问独立测试数据库。
- [ ] Ruff format、Ruff check、Pyright、单元和集成测试全部通过。
- [ ] 真实 HTTP CRUD 验收通过。
- [ ] README 命令可从干净环境复现。
- [ ] 八个口述问题完成，学习进度记录真实更新。

## 官方参考

- SQLAlchemy 2.0 asyncio：<https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- SQLAlchemy Engine 与连接池：<https://docs.sqlalchemy.org/en/20/core/engines.html>
- Alembic asyncio cookbook：<https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic>
- PostgreSQL 官方镜像：<https://hub.docker.com/_/postgres>
