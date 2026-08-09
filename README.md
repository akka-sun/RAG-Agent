# RAG Agent

RAG Agent 是一个用于学习和验证 Agentic RAG 核心链路的后端项目。当前实现以 FastAPI 提供 API，以 ARQ Worker 异步摄取文档，并使用 PostgreSQL 保存业务状态、MinIO 保存原文和解析结果、Redis 承载 ARQ 队列、Milvus 保存生产级文档分块索引。

## 已实现能力

- 知识库的创建、查询、列表与删除。
- `.md`、`.txt` 文件上传，以及异步解析、分块、向量化和索引。
- 摄取任务状态与进度查询，失败任务重试。
- 文档列表、详情、原文下载、解析结果下载与一致性删除。
- Milvus Dense + BM25 双路召回、RRF 融合、去重与远程 Reranker API。
- `/rag/query` 通过混合检索返回稳定 `[S1]` 引用。
- 生产模式可通过 OpenAI-compatible Embedding API 写入真实向量；本地开发未配置 key 时保留 Hashing Embedding，避免默认测试消耗外部额度。
- 数据库迁移，以及单元、集成和端到端测试。

## 项目架构

```mermaid
flowchart LR
    Client["客户端 / Swagger UI"] --> API["FastAPI API"]
    API --> PG[("PostgreSQL<br/>知识库、文档、任务状态")]
    API --> MinIO[("MinIO<br/>原文、解析结果")]
    API --> Redis[("Redis<br/>ARQ 队列")]
    API --> Milvus[("Milvus<br/>Dense Vector、BM25、引用元数据")]
    API --> Models["外部模型 API<br/>Embedding / Reranker"]
    Redis --> Worker["ARQ Worker"]
    Worker --> PG
    Worker --> MinIO
    Worker --> Milvus
    Worker --> Models
```

长期运行的服务包括 `api`、`worker`、`postgres`、`redis`、`minio`、`milvus-etcd`、`milvus-minio` 和 `milvus-standalone`。`minio-init` 是一次性初始化服务，负责创建业务对象存储桶。

### 异步摄取数据流

1. 客户端通过 multipart 请求上传文档。
2. API 校验文件，将原文写入 MinIO，并在 PostgreSQL 创建文档和摄取任务记录。
3. API 将任务写入 Redis ARQ 队列并返回 `202 Accepted`，响应包含文档 ID 和任务 ID。
4. Worker 领取任务，从 MinIO 读取 UTF-8 原文，依次执行解析、分块、Embedding 和 Milvus 索引。
5. Worker 将解析结果写回 MinIO、将文档分块写入 Milvus，并在 PostgreSQL 更新任务阶段、进度和最终状态。
6. 客户端通过摄取任务接口查询 `pending`、`processing`、`completed` 或 `failed` 状态。
7. 删除或重试文档时，系统先按知识库和文档 ID 清理 Milvus chunk，再清理对象存储和数据库状态。

### 混合检索数据流

1. `/rag/query` 先确认知识库存在。
2. API 调用 OpenAI-compatible Embedding API 获取查询向量。
3. Milvus 在同一知识库过滤条件下执行 dense vector 搜索和 BM25 sparse 搜索。
4. 服务使用 RRF 融合两路候选并按 chunk ID 去重。
5. 候选发送到远程 Reranker API，返回最终排序。
6. API 返回答案占位文本和带文档 ID、chunk ID、文件名、字符范围、score 的引用列表。

## 环境要求

- Docker Desktop 或兼容的 Docker Engine
- Docker Compose v2
- PowerShell 7 或 Windows PowerShell 5.1

首次部署时从仓库示例生成本地配置：

```powershell
Copy-Item .env.example .env
```

`.env` 包含应用名称、API 前缀、PostgreSQL、Redis、MinIO、Milvus 连接参数、外部 Embedding/Reranker API 参数，以及宿主机暴露端口。Compose 内部服务名已写入示例配置；本地开发可按需修改密码和端口。不要提交包含真实凭据的 `.env`。

关键外部服务变量：

| 变量 | 用途 |
| --- | --- |
| `RAG_AGENT_MILVUS_URI` | API/worker 访问 Milvus 的地址，Compose 内默认 `http://milvus-standalone:19530` |
| `RAG_AGENT_MILVUS_COLLECTION` | 文档分块 Collection 名称 |
| `RAG_AGENT_OPENAI_BASE_URL` | OpenAI-compatible Embedding API Base URL |
| `RAG_AGENT_OPENAI_API_KEY` | Embedding API Key |
| `RAG_AGENT_EMBEDDING_MODEL` | Embedding 模型名 |
| `RAG_AGENT_EMBEDDING_DIMENSION` | Milvus dense vector 维度，必须与模型输出一致 |
| `RAG_AGENT_RERANK_BASE_URL` | Reranker API Base URL；客户端会请求 `{base}/rerank` |
| `RAG_AGENT_RERANK_API_KEY` | Reranker API Key |
| `RAG_AGENT_RERANK_MODEL` | Reranker 模型名 |

默认入口：

| 服务 | 地址 |
| --- | --- |
| API | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| MinIO API | `http://127.0.0.1:9000` |
| MinIO Console | `http://127.0.0.1:9001` |
| Milvus gRPC/HTTP | `127.0.0.1:19530` |
| Milvus health/Web | `http://127.0.0.1:9091/healthz` |

## Docker Compose 部署

在仓库根目录执行以下命令。

检查 Compose 配置并构建镜像：

```powershell
docker compose config --quiet
docker compose build api worker
```

启动完整服务栈：

```powershell
docker compose up -d
```

应用数据库迁移：

```powershell
docker compose exec api uv run --no-sync alembic upgrade head
```

检查容器与健康状态，并验证 API 存活：

```powershell
docker compose ps --all
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
```

`api`、`worker`、`postgres`、`redis`、`minio`、`milvus-etcd`、`milvus-minio` 和 `milvus-standalone` 应处于 `running` 或 `healthy` 状态，`minio-init` 应成功退出。

查看日志：

```powershell
docker compose logs --tail 100 api worker
docker compose logs -f worker
```

停止服务但保留数据卷：

```powershell
docker compose down
```

## API

启动后可访问 [Swagger UI](http://127.0.0.1:8000/docs) 或 [OpenAPI JSON](http://127.0.0.1:8000/openapi.json)。默认 API 前缀为 `/api/v1`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health/live` | 存活检查 |
| `POST` / `GET` | `/knowledge-bases` | 创建 / 列出知识库 |
| `GET` / `DELETE` | `/knowledge-bases/{knowledge_base_id}` | 查询 / 删除知识库 |
| `POST` / `GET` | `/knowledge-bases/{knowledge_base_id}/documents` | 异步上传 / 列出文档 |
| `GET` / `DELETE` | `/knowledge-bases/{knowledge_base_id}/documents/{document_id}` | 查询 / 删除文档 |
| `GET` | `/knowledge-bases/{knowledge_base_id}/documents/{document_id}/source` | 下载原文 |
| `GET` | `/knowledge-bases/{knowledge_base_id}/documents/{document_id}/parsed` | 下载解析结果 |
| `POST` | `/knowledge-bases/{knowledge_base_id}/documents/{document_id}/retry` | 重试失败摄取 |
| `GET` | `/ingestion-tasks/{task_id}` | 查询摄取任务状态与进度 |
| `POST` | `/rag/documents` | 同步摄取文本到进程内示例索引 |
| `POST` | `/rag/query` | 查询 Milvus 混合检索索引并返回引用 |

## 质量检查

服务栈健康且迁移完成后，在仓库根目录执行：

```powershell
docker compose exec api uv run --no-sync ruff format --check app tests
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
```

真实外部 API 验证默认关闭，避免误消耗额度。配置好真实 Embedding、Reranker 等服务后再显式运行：

```powershell
docker compose exec api uv run --no-sync pytest -m external -v
```

## 当前限制

- 文件上传仅支持非空 `.md` 和 `.txt`，单文件最大 5 MiB；Worker 按 UTF-8 解码原文。
- 阶段 4 已完成真实 Milvus 混合检索；生成式回答、LangGraph Agent、SSE 会话流、PDF 解析器、Langfuse Trace 和评估报告仍在后续阶段。
- 未配置真实外部 API key 时，本地开发/测试路径不会调用付费模型服务；生产部署应设置 `RAG_AGENT_APP_ENV=production` 并配置真实 Embedding/Reranker 凭据。
- `/rag/documents` 保留为早期阶段的同步演示入口；生产文档摄取应使用 `/knowledge-bases/{knowledge_base_id}/documents`。
- Compose 配置面向本地开发，包含源码挂载、热重载和默认开发凭据；生产部署需要独立的密钥、网络、备份、TLS 与可观测性配置。
