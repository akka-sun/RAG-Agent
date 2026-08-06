# RAG Agent

一个用于从零学习 Agentic RAG 核心实现的后端项目。当前已完成阶段 3：FastAPI 接收文档后将任务交给 ARQ Worker，PostgreSQL 保存业务状态，MinIO 保存原文和解析结果，Redis 保存队列及共享文档索引。

## 环境要求

- Docker Desktop
- Docker Compose

## 启动与迁移

```powershell
Copy-Item .env.example .env
docker compose up -d --build postgres redis minio minio-init api worker
docker compose exec api uv run --no-sync alembic upgrade head
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
```

长期运行的 `postgres`、`redis`、`minio`、`api` 和 `worker` 应处于 running/healthy 状态。

## 异步文档摄取

下面的 PowerShell 示例先创建知识库，再上传 Markdown。上传接口返回 `202 Accepted`，表示原文已保存、任务已建档并进入队列，不表示 Worker 已处理成功。

```powershell
$kb = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/knowledge-bases `
  -ContentType 'application/json' `
  -Body '{"name":"demo","description":"async ingestion","embedding_model":"hashing","embedding_dimension":256}'

$accepted = curl.exe -sS -X POST `
  -F "file=@README.md;type=text/markdown" `
  "http://127.0.0.1:8000/api/v1/knowledge-bases/$($kb.id)/documents" |
  ConvertFrom-Json
```

轮询任务，直到 `status` 变为 `completed` 或 `failed`：

```powershell
do {
  Start-Sleep -Milliseconds 500
  $task = Invoke-RestMethod `
    "http://127.0.0.1:8000/api/v1/ingestion-tasks/$($accepted.task_id)"
  $task | Select-Object status, stage, progress, error
} while ($task.status -in @('pending', 'processing'))
```

查询文档并下载原文、解析结果：

```powershell
$documentUrl = "http://127.0.0.1:8000/api/v1/knowledge-bases/$($kb.id)/documents/$($accepted.document_id)"
Invoke-RestMethod $documentUrl
Invoke-WebRequest "$documentUrl/source" -OutFile source.md
Invoke-WebRequest "$documentUrl/parsed" -OutFile parsed.json
```

失败文档会创建一个新的摄取任务，旧任务仍保留为历史记录：

```powershell
$retryTask = Invoke-RestMethod -Method Post "$documentUrl/retry"
```

删除按 Redis 索引、解析对象、原文对象、数据库记录的顺序执行；任一外部清理失败时不会提交数据库删除：

```powershell
Invoke-RestMethod -Method Delete $documentUrl
```

## 阶段 2 最小离线 RAG

- `POST /api/v1/rag/documents`：同步摄取 Markdown/TXT JSON 文本。
- `POST /api/v1/rag/query`：使用确定性 Hashing Embedding 检索并返回本地引用答案。

阶段 2 索引只保存在 API 进程内，用于学习分块、向量检索和引用数据流，不代表生产级存储或真实语义模型质量。

## 检查

```powershell
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
docker compose logs worker --tail 100
```
