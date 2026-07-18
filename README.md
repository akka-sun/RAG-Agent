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