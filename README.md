# RAG Agent

一个用于从零学习 Agentic RAG 核心实现的后端项目。当前已完成阶段 2，包含配置加载、FastAPI、PostgreSQL、知识库 CRUD，以及可确定测试的进程内最小 RAG。

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

## 阶段 2 最小离线 RAG

- `POST /api/v1/rag/documents`：同步摄取 Markdown/TXT JSON 文本。
- `POST /api/v1/rag/query`：使用确定性 Hashing Embedding 检索并返回本地引用回答。

阶段 2 的索引只保存在 API 进程内，服务重启后会丢失。它用于学习分块、向量检索和引用数据流，不代表生产级存储或真实语义模型质量。
