# RAG Agent

一个用于从零学习 Agentic RAG 核心实现的后端项目。当前已完成阶段 1，包含配置加载、FastAPI 应用、健康检查、PostgreSQL、Alembic 迁移和知识库 CRUD API。

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
