# 阶段 0：Python 后端工程基础实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一个可在 Docker Compose 中运行、具备类型安全配置、FastAPI 健康检查、自动化测试和代码质量检查的独立 `RAG-Agent` Python 后端骨架。

**Architecture:** 本阶段只创建一个 `api` 容器和最小 `app` 包，不接入数据库、Redis、Milvus 或模型服务。配置由 Pydantic Settings 从环境变量读取，FastAPI 应用通过工厂函数创建，健康检查只证明进程可用；后续阶段将在该边界上增加基础设施。

**Tech Stack:** Python 3.12、uv、FastAPI、Uvicorn、Pydantic Settings、pytest、HTTPX、Ruff、Pyright、Docker Compose。

## Global Constraints

- 项目目录固定为 `RAG-Agent/`，不得导入 `backend/package/yuxi`。
- Python 版本范围为 `>=3.12,<3.14`。
- 所有开发、测试和检查命令在 Docker Compose 的 `api` 容器中运行。
- 代码标识符使用英文；文档、注释和 API 描述使用中文。
- 使用测试驱动开发：先观察目标测试失败，再写最小实现使其通过。
- 本阶段不增加数据库、队列、向量库、模型客户端、统一响应包装或复杂异常体系。
- 每个任务由学习者独立实现并通过代码审查、测试和口述验收后再提交。

---

## 文件结构

本阶段结束时目录如下：

```text
RAG-Agent/
├── app/
│   ├── __init__.py
│   ├── config.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       ├── test_config.py
│       └── test_health.py
├── docs/
│   ├── design.md
│   ├── learning-roadmap.md
│   └── plans/
│       └── 2026-07-17-stage-0-foundation.md
├── .dockerignore
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

职责：

- `app/config.py`：唯一的应用配置入口。
- `app/main.py`：创建 FastAPI 应用并定义当前唯一的健康检查路由。
- `tests/unit/test_config.py`：验证环境变量到强类型配置的映射。
- `tests/unit/test_health.py`：验证应用元数据与健康接口响应契约。
- `Dockerfile`：定义开发和测试共用的 Python 镜像。
- `docker-compose.yml`：定义本阶段唯一的 `api` 服务和热重载命令。
- `pyproject.toml`：依赖、测试、格式化、Lint 和类型检查配置。

### Task 1: 建立可执行的容器化 Python 项目

**Files:**

- Create: `RAG-Agent/pyproject.toml`
- Create: `RAG-Agent/Dockerfile`
- Create: `RAG-Agent/docker-compose.yml`
- Create: `RAG-Agent/.dockerignore`
- Create: `RAG-Agent/README.md`
- Create: `RAG-Agent/app/__init__.py`
- Create: `RAG-Agent/tests/__init__.py`
- Create: `RAG-Agent/tests/unit/__init__.py`

**Interfaces:**

- Consumes: Docker Desktop、Docker Compose 与 NVIDIA 无关的基础 Python 运行环境。
- Produces: 可通过 `docker compose run --rm api python --version` 执行 Python 3.12 的 `api` 服务；后续任务在该容器内运行测试。

- [ ] **Step 1: 创建项目元数据与依赖配置**

创建 `RAG-Agent/pyproject.toml`：

```toml
[project]
name = "rag-agent"
version = "0.1.0"
description = "用于学习 Agentic RAG 核心实现的后端项目"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = [
    "fastapi>=0.121",
    "pydantic-settings>=2.10",
    "uvicorn[standard]>=0.34.2",
]

[dependency-groups]
dev = [
    "pyright>=1.1.400",
    "ruff>=0.12.1",
]
test = [
    "httpx>=0.28",
    "pytest>=8.0",
]

[tool.pytest.ini_options]
addopts = "-v --tb=short"
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "unit: 不访问真实外部服务的单元测试",
    "integration: 访问真实基础设施的集成测试",
    "e2e: 覆盖完整业务链路的端到端测试",
    "external: 依赖真实外部模型或解析服务的测试",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
include = ["app", "tests"]
```

- [ ] **Step 2: 创建最小 Python 包目录**

创建空文件：

```python
# RAG-Agent/app/__init__.py
```

```python
# RAG-Agent/tests/__init__.py
```

```python
# RAG-Agent/tests/unit/__init__.py
```

创建最小 `RAG-Agent/README.md`，使项目元数据在镜像构建时引用有效文件：

```markdown
# RAG Agent
```

- [ ] **Step 3: 创建开发镜像**

创建 `RAG-Agent/Dockerfile`：

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/
COPY pyproject.toml ./
COPY README.md ./

RUN uv sync --no-install-project --group dev --group test

COPY app ./app
COPY tests ./tests

CMD ["python", "--version"]
```

- [ ] **Step 4: 创建 Compose 开发服务**

创建 `RAG-Agent/docker-compose.yml`：

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    working_dir: /app
    volumes:
      - ./app:/app/app
      - ./tests:/app/tests
    command: python --version
```

创建 `RAG-Agent/.dockerignore`：

```text
.git
.venv
__pycache__
.pytest_cache
.ruff_cache
.pyright
*.pyc
.env
docs
```

- [ ] **Step 5: 构建镜像并验证 Python 版本**

在 `RAG-Agent/` 中运行：

```powershell
docker compose build api
docker compose run --rm api python --version
```

预期：镜像构建成功，第二条命令输出 `Python 3.12.x`。

- [ ] **Step 6: 验证依赖可导入**

运行：

```powershell
docker compose run --rm api uv run --no-sync python -c "import fastapi, pydantic_settings; print('dependencies ready')"
```

预期：输出 `dependencies ready`。

- [ ] **Step 7: 提交容器化项目骨架**

```powershell
git add RAG-Agent/pyproject.toml RAG-Agent/Dockerfile RAG-Agent/docker-compose.yml RAG-Agent/.dockerignore RAG-Agent/README.md RAG-Agent/app/__init__.py RAG-Agent/tests/__init__.py RAG-Agent/tests/unit/__init__.py
git commit -m "chore: 初始化 RAG Agent 后端工程"
```

### Task 2: 用测试驱动实现强类型配置

**Files:**

- Create: `RAG-Agent/tests/unit/test_config.py`
- Create: `RAG-Agent/app/config.py`
- Create: `RAG-Agent/.env.example`

**Interfaces:**

- Consumes: Task 1 提供的 Python 容器和 `pydantic-settings` 依赖。
- Produces: `Settings(BaseSettings)`、字段 `app_name: str`、`app_env: Literal["development", "test", "production"]`、`debug: bool`、`api_v1_prefix: str`，以及无参数函数 `get_settings() -> Settings`。

- [ ] **Step 1: 编写配置加载失败测试**

创建 `RAG-Agent/tests/unit/test_config.py`：

```python
import pytest

from app.config import Settings


def test_settings_read_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_AGENT_APP_NAME", "测试 RAG")
    monkeypatch.setenv("RAG_AGENT_APP_ENV", "test")
    monkeypatch.setenv("RAG_AGENT_DEBUG", "true")
    monkeypatch.setenv("RAG_AGENT_API_V1_PREFIX", "/custom-api")

    settings = Settings(_env_file=None)

    assert settings.app_name == "测试 RAG"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.api_v1_prefix == "/custom-api"
```

- [ ] **Step 2: 运行测试并确认失败原因正确**

运行：

```powershell
docker compose run --rm api uv run --no-sync pytest tests/unit/test_config.py -v
```

预期：测试收集失败，错误包含 `ModuleNotFoundError: No module named 'app.config'`。

- [ ] **Step 3: 实现最小配置类**

创建 `RAG-Agent/app/config.py`：

```python
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RAG_AGENT_",
        extra="ignore",
    )

    app_name: str = "RAG Agent"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 运行配置测试并确认通过**

```powershell
docker compose run --rm api uv run --no-sync pytest tests/unit/test_config.py -v
```

预期：`1 passed`。

- [ ] **Step 5: 创建环境变量示例**

创建 `RAG-Agent/.env.example`：

```dotenv
RAG_AGENT_APP_NAME=RAG Agent
RAG_AGENT_APP_ENV=development
RAG_AGENT_DEBUG=false
RAG_AGENT_API_V1_PREFIX=/api/v1
```

- [ ] **Step 6: 运行 Ruff 和 Pyright**

```powershell
docker compose run --rm api uv run --no-sync ruff check app tests
docker compose run --rm api uv run --no-sync pyright
```

预期：Ruff 输出 `All checks passed!`；Pyright 输出 `0 errors`。

- [ ] **Step 7: 提交配置实现**

```powershell
git add RAG-Agent/app/config.py RAG-Agent/tests/unit/test_config.py RAG-Agent/.env.example
git commit -m "feat: 增加应用配置加载"
```

### Task 3: 用测试驱动实现 FastAPI 健康检查

**Files:**

- Create: `RAG-Agent/tests/unit/test_health.py`
- Create: `RAG-Agent/app/main.py`
- Modify: `RAG-Agent/docker-compose.yml`

**Interfaces:**

- Consumes: `get_settings() -> Settings` 及 `Settings.app_name`、`Settings.debug`、`Settings.api_v1_prefix`。
- Produces: `create_app() -> FastAPI`、模块级 `app: FastAPI`、`GET /api/v1/health/live`，响应固定为 `{"status": "ok"}`。

- [ ] **Step 1: 编写应用与健康检查测试**

创建 `RAG-Agent/tests/unit/test_health.py`：

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_uses_configured_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_AGENT_APP_NAME", "测试应用")
    monkeypatch.setenv("RAG_AGENT_DEBUG", "true")

    app = create_app()

    assert app.title == "测试应用"
    assert app.debug is True


def test_live_health_returns_process_status() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试并确认失败原因正确**

```powershell
docker compose run --rm api uv run --no-sync pytest tests/unit/test_health.py -v
```

预期：测试收集失败，错误包含 `ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 3: 实现应用工厂与健康检查**

创建 `RAG-Agent/app/main.py`：

```python
from typing import Literal, TypedDict

from fastapi import APIRouter, FastAPI

from app.config import get_settings


class HealthResponse(TypedDict):
    status: Literal["ok"]


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, debug=settings.debug)
    router = APIRouter(prefix=settings.api_v1_prefix)

    @router.get("/health/live", tags=["系统"])
    async def live_health() -> HealthResponse:
        return {"status": "ok"}

    application.include_router(router)
    return application


app = create_app()
```

- [ ] **Step 4: 运行测试并处理配置缓存隔离**

先运行：

```powershell
docker compose run --rm api uv run --no-sync pytest tests/unit/test_health.py -v
```

如果 `test_create_app_uses_configured_metadata` 因 `get_settings()` 缓存读取了旧环境而失败，在测试文件中增加自动 fixture：

```python
from collections.abc import Iterator

from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

再次运行同一命令。

预期：`2 passed`。这个 fixture 是测试隔离，不应放进生产代码。

- [ ] **Step 5: 将 Compose 命令改为热重载 API**

将 `RAG-Agent/docker-compose.yml` 更新为：

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rag-agent-api-dev
    working_dir: /app
    volumes:
      - ./app:/app/app
      - ./tests:/app/tests
    ports:
      - "127.0.0.1:8000:8000"
    env_file:
      - path: .env
        required: false
    command: >
      uv run --no-sync uvicorn app.main:app
      --host 0.0.0.0
      --port 8000
      --reload
      --reload-dir /app/app
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live').read()
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s
```

- [ ] **Step 6: 启动 API 并验证真实 HTTP 接口**

```powershell
docker compose up -d api
docker compose ps
docker compose logs api --tail 50
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
```

预期：

- `docker compose ps` 最终显示 `api` 为 `healthy`。
- 日志中没有 traceback。
- PowerShell 返回包含 `status` 值 `ok` 的对象。

- [ ] **Step 7: 运行当前全部测试**

```powershell
docker compose exec api uv run --no-sync pytest tests/unit -v
```

预期：`3 passed`。

- [ ] **Step 8: 提交 FastAPI 应用**

```powershell
git add RAG-Agent/app/main.py RAG-Agent/tests/unit/test_health.py RAG-Agent/docker-compose.yml
git commit -m "feat: 增加 API 存活检查"
```

### Task 4: 完成阶段 0 的质量门槛与学习文档

**Files:**

- Modify: `RAG-Agent/README.md`
- Modify: `RAG-Agent/docs/learning-roadmap.md`

**Interfaces:**

- Consumes: Task 1～3 提供的容器、配置、API 和测试命令。
- Produces: 可由新学习者复现的启动说明，以及阶段 0 的测试和口述验收记录。

- [ ] **Step 1: 编写最小启动文档**

创建 `RAG-Agent/README.md`：

```markdown
# RAG Agent

一个用于从零学习 Agentic RAG 核心实现的后端项目。当前处于阶段 0，仅包含配置加载、FastAPI 应用、健康检查和工程质量工具。

## 环境要求

- Docker Desktop
- Docker Compose

## 启动

```powershell
Copy-Item .env.example .env
docker compose up -d --build api
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
```

Swagger 地址：`http://127.0.0.1:8000/docs`

## 检查

```powershell
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync ruff format --check app tests
docker compose exec api uv run --no-sync ruff check app tests
docker compose exec api uv run --no-sync pyright
```
```

- [ ] **Step 2: 执行格式检查、测试、Lint 与类型检查**

```powershell
docker compose exec api uv run --no-sync ruff format --check app tests
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync ruff check app tests
docker compose exec api uv run --no-sync pyright
```

预期：

- Ruff format 输出文件均已格式化。
- pytest 输出 `3 passed`。
- Ruff check 输出 `All checks passed!`。
- Pyright 输出 `0 errors`。

- [ ] **Step 3: 验证热重载**

暂时将 `app/main.py` 中响应值改成 `{"status": "changed"}`，保存后查看日志：

```powershell
docker compose logs api --tail 20
```

预期：日志出现 reload 信息。立即把响应恢复为 `{"status": "ok"}`，再次请求并确认恢复。这个步骤只用于观察热重载，不提交临时改动。

- [ ] **Step 4: 完成口述验收**

不看文档回答以下问题，并由指导者检查：

1. `Dockerfile` 与 `docker-compose.yml` 分别解决什么问题？
2. 为什么容器内监听 `0.0.0.0`，宿主机端口却绑定 `127.0.0.1`？
3. `async def live_health()` 在当前实现中为什么没有带来并行收益？
4. Pydantic Settings 如何把字符串 `"true"` 转换成布尔值？
5. 为什么测试修改环境变量后需要清理 `get_settings()` 缓存？
6. `live` 健康检查与后续 `ready` 健康检查有什么区别？
7. 单元测试为什么使用 `TestClient`，而最终还要请求真实容器端口？

验收标准：能用自己的语言说明因果关系；不要求背诵定义。

- [ ] **Step 5: 更新学习进度表**

在 `RAG-Agent/docs/learning-roadmap.md` 的进度表中追加一行，格式如下：

```markdown
| 完成日期 | 阶段 0 | 容器化骨架、配置、健康检查 | pytest、Ruff、Pyright、真实 HTTP 健康检查 | Docker、配置、FastAPI 基础 | 根据代码审查填写 |
```

执行时用真实完成日期替换“完成日期”，用代码审查中实际暴露的问题替换最后一列；不得填写虚构结果。

- [ ] **Step 6: 提交阶段 0 文档与验收记录**

```powershell
git add RAG-Agent/README.md RAG-Agent/docs/learning-roadmap.md
git commit -m "docs: 完善阶段零启动与学习记录"
```

## 阶段 0 完成定义

- [ ] `docker compose up -d --build api` 能启动健康的 API 容器。
- [ ] `GET /api/v1/health/live` 返回 `200` 和 `{"status": "ok"}`。
- [ ] 环境变量可以覆盖强类型配置默认值。
- [ ] 所有新增测试在容器内通过。
- [ ] Ruff format、Ruff check 和 Pyright 均通过。
- [ ] README 中的命令可从干净环境复现。
- [ ] 学习者通过七个口述问题的验收。
- [ ] 没有提前加入数据库、队列、Milvus 或模型相关代码。
