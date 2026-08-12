# 阶段 3：异步文档摄取实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 MinIO、Redis 和 ARQ 建立可查询状态、可重试、可补偿且重复执行不产生重复索引的异步文档摄取链路。

**Architecture:** API 只完成校验、原文件落盘、数据库建档和任务入队，然后返回 202；独立 Worker 认领数据库任务并执行解析、分块、确定性向量化和索引。PostgreSQL 保存业务与任务事实，MinIO 保存文件，Redis 同时承载 ARQ 队列和阶段 3 临时共享索引，所有跨存储失败通过显式状态和补偿处理。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2 async、PostgreSQL、Alembic、MinIO、Redis、ARQ、pytest、httpx、Ruff、Pyright、Docker Compose。

## Global Constraints

- 由学习者编写每个 Task 的核心代码；Codex 在每个 Task 末尾负责格式化、测试、Lint、类型检查、差异审查和 Git 提交。
- 所有运行与验证均在 Docker Compose 容器内完成。
- 每个 Task 遵循测试先行：先看到预期失败，再完成最小实现。
- 只支持 UTF-8 `.md`、`.txt`；单文件上限固定为 5 MiB。
- 不增加 PDF、真实模型、Milvus、自动重试、任务取消或进度推送。
- Route 不直接操作 SQLAlchemy、MinIO、Redis 或 ARQ；事务由 Service 管理。
- PostgreSQL `commit()` 不得被当作跨存储事务；补偿失败必须暴露，不做静默回退。
- 每个 Task 只提交本 Task 文件，提交信息遵循中文 Conventional Commits。

---

## 文件结构

```text
app/
├── api/
│   ├── dependencies.py
│   └── routes/
│       ├── documents.py
│       └── ingestion_tasks.py
├── core/config.py
├── db/
│   ├── models/document.py
│   ├── models/ingestion_task.py
│   └── repositories/
│       ├── documents.py
│       └── ingestion_tasks.py
├── infrastructure/
│   ├── object_storage.py
│   ├── queue.py
│   └── redis_index.py
├── schemas/
│   ├── documents.py
│   └── ingestion_tasks.py
├── services/
│   ├── documents.py
│   └── ingestion.py
└── worker.py
alembic/versions/*_add_documents_and_ingestion_tasks.py
tests/
├── unit/
│   ├── test_document_schemas.py
│   ├── test_document_service.py
│   ├── test_ingestion_service.py
│   └── test_redis_index.py
└── integration/
    ├── test_documents_api.py
    └── test_ingestion_worker.py
```

---

### Task 1：启动 Redis、MinIO 与 Worker

**目标：** 建立跨进程异步处理所需基础设施，并能通过健康检查确认四个服务可用。

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `app/core/config.py`
- Modify: `docker-compose.yml`
- Create: `app/worker.py`
- Modify: `.env.example`

**Interfaces:**

- Produces: `settings.redis_url`、`settings.minio_endpoint`、`settings.minio_access_key`、`settings.minio_secret_key`、`settings.minio_bucket`
- Produces: `WorkerSettings`，初始仅注册 `health_job`

- [ ] **Step 1：添加依赖和配置**

依赖固定在同一兼容范围：

```toml
"arq>=0.28,<0.29",
"minio>=7.2,<8",
"python-multipart>=0.0.20,<1",
```

配置字段：

```python
redis_url: str = "redis://redis:6379/0"
minio_endpoint: str = "minio:9000"
minio_access_key: str = "rag-agent"
minio_secret_key: str = "rag-agent-secret"
minio_bucket: str = "rag-agent"
```

- [ ] **Step 2：添加 Compose 服务**

增加 `redis`、`minio`、一次性 `minio-init` 和 `worker`；`worker` 使用与 API 相同镜像和源码挂载，命令为：

```yaml
command: ["uv", "run", "--no-sync", "arq", "app.worker.WorkerSettings"]
```

Redis 使用 `redis:8-alpine`，MinIO 使用 `minio/minio`，都配置健康检查；API 和 Worker 等待 PostgreSQL、Redis、MinIO 健康。

- [ ] **Step 3：创建最小 Worker**

```python
async def health_job(ctx: dict[str, object]) -> str:
    return "ok"


class WorkerSettings:
    functions = [health_job]
```

- [ ] **Step 4：由 Codex 检查并提交**

验收命令：

```bash
docker compose config
docker compose up -d --build postgres redis minio minio-init api worker
docker compose ps
docker compose exec api uv run --no-sync python -c "import arq, minio; print('dependencies ok')"
```

预期：所有长期服务为 running/healthy，依赖导入成功。

提交：`chore: 增加异步摄取基础设施`

---

### Task 2：文档与摄取任务数据模型

**目标：** PostgreSQL 能持久保存文档及每次摄取尝试，并用约束保护状态和关联关系。

**Files:**

- Create: `app/db/models/document.py`
- Create: `app/db/models/ingestion_task.py`
- Modify: `app/db/models/__init__.py`
- Modify: `app/db/models/knowledge_base.py`
- Create: `alembic/versions/<revision>_add_documents_and_ingestion_tasks.py`
- Create: `tests/unit/test_ingestion_models.py`

**Interfaces:**

```python
class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStage(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
```

- [ ] **Step 1：先写模型测试**

测试必须验证：默认状态、默认进度、文档与知识库关系、任务与文档关系、`progress` 数据库约束以及删除非空知识库失败。

- [ ] **Step 2：创建模型**

`Document` 至少包含：

```text
id, knowledge_base_id, filename, content_type, size_bytes,
source_object_key, parsed_object_key, status, chunk_count,
error, created_at, updated_at
```

`IngestionTask` 至少包含：

```text
id, document_id, arq_job_id, status, stage, progress, error,
created_at, started_at, completed_at
```

所有状态存为 `String(32)`；`progress` 使用 `CHECK (progress BETWEEN 0 AND 100)`；外键删除策略使用 `RESTRICT`，任务历史不级联消失。

- [ ] **Step 3：创建并验证迁移**

```bash
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync alembic downgrade -1
docker compose exec api uv run --no-sync alembic upgrade head
```

- [ ] **Step 4：由 Codex 检查并提交**

验收：目标单测、迁移往返、Ruff、Pyright。

提交：`feat: 增加文档与摄取任务模型`

---

### Task 3：Schema、错误与状态迁移规则

**目标：** 先固定 HTTP 输出和合法状态变化，后续 Service 不使用随意字符串。

**Files:**

- Create: `app/schemas/documents.py`
- Create: `app/schemas/ingestion_tasks.py`
- Modify: `app/core/exceptions.py`
- Modify: `app/schemas/errors.py`
- Create: `tests/unit/test_document_schemas.py`

**Interfaces:**

```python
ALLOWED_DOCUMENT_SUFFIXES = {".md", ".txt"}
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024


class DocumentAcceptedResponse(BaseModel):
    document_id: UUID
    task_id: UUID
    status: Literal["pending"]


class DocumentResponse(BaseModel): ...


class IngestionTaskResponse(BaseModel): ...
```

错误码固定为：

```text
DOCUMENT_NOT_FOUND
INGESTION_TASK_NOT_FOUND
UNSUPPORTED_DOCUMENT
DOCUMENT_TOO_LARGE
DOCUMENT_NOT_RETRYABLE
DOCUMENT_STORAGE_UNAVAILABLE
INGESTION_QUEUE_UNAVAILABLE
DOCUMENT_CLEANUP_FAILED
```

- [ ] **Step 1：写验证测试**

覆盖大小边界、扩展名大小写、空文件名、响应序列化和非法状态迁移。

- [ ] **Step 2：实现最小 Schema 与异常**

文件验证函数保持纯函数：

```python
def validate_upload(filename: str | None, content: bytes) -> str:
    if not filename or Path(filename).suffix.lower() not in ALLOWED_DOCUMENT_SUFFIXES:
        raise UnsupportedDocumentError
    if not content:
        raise UnsupportedDocumentError
    if len(content) > MAX_DOCUMENT_SIZE:
        raise DocumentTooLargeError
    return Path(filename).name
```

- [ ] **Step 3：由 Codex检查并提交**

提交：`feat: 定义异步摄取接口契约`

---

### Task 4：文档与任务 Repository

**目标：** 将查询和并发认领集中在 Repository，Service 负责决定何时提交。

**Files:**

- Create: `app/db/repositories/documents.py`
- Create: `app/db/repositories/ingestion_tasks.py`
- Create: `tests/unit/test_ingestion_repositories.py`

**Interfaces:**

```python
class DocumentRepository:
    async def add(self, document: Document) -> None: ...
    async def get(
        self, document_id: UUID, knowledge_base_id: UUID | None = None
    ) -> Document | None: ...
    async def list_by_knowledge_base(self, knowledge_base_id: UUID) -> list[Document]: ...
    async def delete(self, document: Document) -> None: ...


class IngestionTaskRepository:
    async def add(self, task: IngestionTask) -> None: ...
    async def get(self, task_id: UUID) -> IngestionTask | None: ...
    async def claim_pending(self, task_id: UUID) -> IngestionTask | None: ...
    async def has_active_task(self, document_id: UUID) -> bool: ...
```

- [ ] **Step 1：先写真实 PostgreSQL Repository 测试**

`claim_pending()` 测试必须连续调用两次：第一次返回 processing 任务，第二次返回 `None`。

- [ ] **Step 2：实现 Repository**

`claim_pending()` 使用带条件的更新或 `SELECT ... FOR UPDATE`，只允许 `pending → processing`，同时设置 `started_at`。Repository 只能 `flush()`，不能 `commit()`。

- [ ] **Step 3：由 Codex 检查并提交**

提交：`feat: 增加文档与任务数据访问层`

---

### Task 5：MinIO 对象存储适配器

**目标：** 用可替换接口隔离同步 MinIO SDK，并验证上传失败后的清理行为。

**Files:**

- Create: `app/infrastructure/object_storage.py`
- Create: `tests/unit/test_object_storage.py`

**Interfaces:**

```python
class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


def source_key(knowledge_base_id: UUID, document_id: UUID, filename: str) -> str: ...
def parsed_key(knowledge_base_id: UUID, document_id: UUID) -> str: ...
```

- [ ] **Step 1：写键名和适配器测试**

键名必须稳定且不接受路径穿越；MinIO SDK 的阻塞调用必须从事件循环移到线程。

- [ ] **Step 2：实现 `MinioObjectStorage`**

使用 `asyncio.to_thread()` 包装 `put_object`、`get_object`、`remove_object`。读取后必须关闭并释放响应连接；初始化时确保 bucket 存在。

- [ ] **Step 3：由 Codex 检查并提交**

提交：`feat: 增加 MinIO 文档存储适配器`

---

### Task 6：ARQ 队列适配器

**目标：** Service 只依赖队列协议，并通过固定 job ID 防止同一任务被重复入队。

**Files:**

- Create: `app/infrastructure/queue.py`
- Modify: `app/api/dependencies.py`
- Create: `tests/unit/test_ingestion_queue.py`

**Interfaces:**

```python
class IngestionQueue(Protocol):
    async def enqueue(self, task_id: UUID, document_id: UUID) -> str: ...


class ArqIngestionQueue:
    async def enqueue(self, task_id: UUID, document_id: UUID) -> str:
        job = await self.redis.enqueue_job(
            "ingest_document",
            str(task_id),
            str(document_id),
            _job_id=str(task_id),
        )
        if job is None:
            raise IngestionQueueUnavailableError
        return job.job_id
```

- [ ] **Step 1：用 Fake Redis 写失败与重复测试**

覆盖正常 job ID、`enqueue_job()` 返回 `None`、连接异常三条路径。

- [ ] **Step 2：实现协议、ARQ 适配器和依赖生命周期**

依赖结束时显式关闭 Redis/ARQ 连接，不把连接池创建在每个业务方法中。

- [ ] **Step 3：由 Codex 检查并提交**

提交：`feat: 增加 ARQ 摄取队列适配器`

---

### Task 7：上传 Service 与 202 API

**目标：** 完成“文件落盘 → 数据库建档 → 入队”的短事务链路和失败补偿。

**Files:**

- Create: `app/services/documents.py`
- Create: `app/api/routes/documents.py`
- Modify: `app/api/dependencies.py`
- Modify: `app/main.py`
- Create: `tests/unit/test_document_service.py`
- Create: `tests/integration/test_documents_api.py`

**Interfaces:**

```python
class DocumentService:
    async def upload(
        self,
        knowledge_base_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> tuple[Document, IngestionTask]: ...
```

- [ ] **Step 1：先写 Service 补偿测试**

至少覆盖：

1. 成功时保存对象、提交数据库、入队并记录 job ID。
2. 数据库提交失败时回滚并删除已上传对象。
3. 入队失败时用新事务把文档和任务标记 failed，保留原文件。

- [ ] **Step 2：实现最小上传 Service**

事务边界必须显式：

```python
await storage.put(key, content, content_type)
try:
    repositories.add(document, task)
    await session.commit()
except Exception:
    await session.rollback()
    await storage.delete(key)
    raise

try:
    task.arq_job_id = await queue.enqueue(task.id, document.id)
    await session.commit()
except Exception as exc:
    await session.rollback()
    await mark_enqueue_failed(document.id, task.id, str(exc))
    raise IngestionQueueUnavailableError from exc
```

- [ ] **Step 3：实现 multipart Route**

Route 只读取 `UploadFile`、调用 Service、映射响应；成功状态码固定 202。

- [ ] **Step 4：由 Codex 检查并提交**

提交：`feat: 增加异步文档上传接口`

---

### Task 8：Redis 临时共享索引

**目标：** Worker 写入、API 或测试进程读取同一索引，并用覆盖写保证文档级幂等。

**Files:**

- Create: `app/infrastructure/redis_index.py`
- Create: `tests/unit/test_redis_index.py`

**Interfaces:**

```python
class RedisDocumentIndex:
    async def replace_document(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        chunks: list[IndexedChunk],
    ) -> None: ...
    async def get_document(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> list[IndexedChunk]: ...
    async def delete_document(self, knowledge_base_id: UUID, document_id: UUID) -> None: ...
```

- [ ] **Step 1：写覆盖与隔离测试**

同一文档连续写两次后只能读到第二批 chunks；不同知识库和文档键互不影响。

- [ ] **Step 2：实现 JSON 序列化索引**

使用一个 Redis `SET` 原子覆盖整个文档索引，不使用 `RPUSH`。键格式固定为：

```python
f"rag:index:{knowledge_base_id}:{document_id}"
```

- [ ] **Step 3：由 Codex 检查并提交**

提交：`feat: 增加共享文档索引`

---

### Task 9：Worker 摄取状态机

**目标：** Worker 能幂等地完成读取、解析、分块、向量化、索引与状态更新。

**Files:**

- Create: `app/services/ingestion.py`
- Modify: `app/worker.py`
- Create: `tests/unit/test_ingestion_service.py`
- Create: `tests/integration/test_ingestion_worker.py`

**Interfaces:**

```python
class IngestionService:
    async def run(self, task_id: UUID, document_id: UUID) -> None: ...


async def ingest_document(
    ctx: dict[str, object],
    task_id: str,
    document_id: str,
) -> None: ...
```

- [ ] **Step 1：写成功、失败和重复执行测试**

验证每个阶段的进度：

```text
parsing=20, chunking=40, embedding=60, indexing=80, completed=100
```

第二次执行同一已完成任务时，对象读取和索引写入次数不得增加。

- [ ] **Step 2：实现成功路径**

Worker 顺序固定：

```text
claim pending task
→ document=processing
→ read UTF-8 source
→ write parsed JSON
→ chunk_text
→ HashingEmbedder
→ RedisDocumentIndex.replace_document
→ document/task=completed
```

每次阶段更新单独提交，使轮询能看到进度；索引成功后最后一次数据库提交记录 `chunk_count` 和 `parsed_object_key`。

- [ ] **Step 3：实现失败路径**

捕获处理异常后先回滚当前事务，再用独立事务把文档和任务标记 failed、保存可读错误。不要自动改回 pending，也不要吞掉异常。

- [ ] **Step 4：注册 Worker 函数和启动/关闭钩子**

`on_startup` 创建数据库 Session factory、MinIO、Redis 索引；`on_shutdown` 关闭 Redis 和数据库资源。

- [ ] **Step 5：由 Codex 检查并提交**

提交：`feat: 实现异步摄取工作流`

---

### Task 10：查询、下载、重试与删除 API

**目标：** 用户能观察任务、取得文件、恢复失败任务并安全删除文档。

**Files:**

- Modify: `app/services/documents.py`
- Modify: `app/api/routes/documents.py`
- Create: `app/api/routes/ingestion_tasks.py`
- Modify: `app/main.py`
- Modify: `tests/integration/test_documents_api.py`

**Interfaces:**

```python
async def list_documents(knowledge_base_id: UUID) -> list[Document]: ...
async def get_document(knowledge_base_id: UUID, document_id: UUID) -> Document: ...
async def retry(knowledge_base_id: UUID, document_id: UUID) -> IngestionTask: ...
async def delete(knowledge_base_id: UUID, document_id: UUID) -> None: ...
async def download_source(...) -> tuple[str, str, bytes]: ...
async def download_parsed(...) -> bytes: ...
async def get_task(task_id: UUID) -> IngestionTask: ...
```

- [ ] **Step 1：写 API 集成测试**

覆盖列表/详情、任务轮询、下载、只允许 failed 文档重试、不存在资源 404、删除后数据库/MinIO/Redis 均不存在。

- [ ] **Step 2：实现重试**

重试不复用旧任务；先确认文档为 failed 且没有 active task，再新建 pending 任务、清空文档错误并入队。入队失败沿用 Task 7 的失败标记。

- [ ] **Step 3：实现删除补偿**

按“索引 → parsed 对象 → source 对象 → 数据库”清理。任一外部清理失败时不提交数据库删除，并返回 `DOCUMENT_CLEANUP_FAILED`。

- [ ] **Step 4：实现只读接口**

下载原文件使用原始文件名和 content type；解析结果未生成时返回明确冲突错误，不返回空 JSON。

- [ ] **Step 5：由 Codex 检查并提交**

提交：`feat: 完善文档任务管理接口`

---

### Task 11：端到端验收与学习复盘

**目标：** 在真实容器边界内证明异步、状态、幂等和补偿行为，而不只证明 Mock 能工作。

**Files:**

- Create: `tests/e2e/test_async_ingestion.py`
- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`

- [ ] **Step 1：编写真实 E2E**

流程：

```text
创建知识库
→ multipart 上传 Markdown，断言 202
→ 轮询任务直到 completed
→ 下载原文与解析结果
→ 检查 chunk_count 和 Redis 索引
→ 再次调用同一 task，断言 chunk 数不变
→ 删除文档，确认对象/索引/数据库清理
```

轮询必须有固定超时；超时打印 API 与 Worker 最近日志，不无限等待。

- [ ] **Step 2：Codex 执行完整检查**

```bash
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
docker compose logs worker --tail 100
```

- [ ] **Step 3：学习者口述验收**

1. 为什么上传成功用 202，而任务仍可能失败？
2. `flush()`、`commit()`、`rollback()` 在异步摄取中分别负责什么？
3. 数据库已提交但入队失败时，为什么保留 MinIO 原文件？
4. Worker 为什么要先 claim，不能收到消息就直接执行？
5. 为什么 Redis 文档索引使用覆盖写，而不是追加？
6. 删除跨三个存储时，为什么不能先删除数据库记录？
7. ARQ 的 job 唯一性与数据库任务状态分别解决什么问题？

- [ ] **Step 4：更新文档并由 Codex 提交**

README 增加启动、上传、轮询、重试和删除示例；路线图只记录真实通过的检查。

提交：`docs: 完善阶段三异步摄取学习记录`

---

## 每个 Task 的固定协作方式

1. Codex 解释本 Task 的数据流、给出完整代码和第一个失败测试。
2. 学习者在容器内完成代码并贴出目标测试结果或错误。
3. Codex 根据错误逐步指导，直到目标测试通过。
4. 学习者说“完成”后停止修改。
5. Codex 执行格式化、目标测试、相关回归、Ruff、Pyright 和 diff 审查。
6. 检查通过后 Codex 只提交该 Task 的文件，并报告提交号。
7. 再进入下一个 Task。

阶段三全部 Task 完成后，Codex 再执行一次全量端到端验收并推送 GitHub。

