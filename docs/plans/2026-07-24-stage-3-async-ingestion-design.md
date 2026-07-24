# 阶段 3：异步文档摄取设计

日期：2026-07-24

## 1. 学习目标

把阶段 2 的“请求内同步处理文本”升级为一条可恢复的异步摄取流水线：

```text
上传文件
  → MinIO 保存原文件
  → PostgreSQL 保存文档与任务
  → ARQ 将任务写入 Redis
  → Worker 解析、分块、向量化、建立共享索引
  → API 查询任务进度或执行重试/删除
```

完成后应能解释：

1. API 为什么返回 `202 Accepted`，而不是等待摄取完成。
2. PostgreSQL、MinIO、Redis 无法共享一个数据库事务时，如何通过状态和补偿保证最终一致。
3. `pending → processing → completed/failed` 状态为何只能按规则迁移。
4. Worker 重复收到同一任务时，如何避免产生重复的可检索 chunk。
5. `commit()` 只提交数据库事务，为什么不能代表文件、队列和索引也成功。

## 2. 范围

### 本阶段实现

- Docker Compose 增加 Redis、MinIO 和 ARQ Worker。
- `.md`、`.txt` 的 multipart 文件上传，成功入队返回 202。
- `documents`、`ingestion_tasks` PostgreSQL 表和 Alembic 迁移。
- MinIO 保存原文件和解析后的 JSON。
- ARQ 负责异步投递和 Worker 执行。
- 任务详情、文档列表/详情、原文件下载、解析结果下载。
- 失败原因、人工重试和文档删除。
- 条件更新与行锁实现任务认领，固定任务 ID 实现幂等投递。
- Redis 临时共享 chunk 索引，使 API 与 Worker 跨进程共享结果。
- 上传、入队、处理、删除各阶段的失败测试和补偿。

### 本阶段不实现

- PDF、Word、网页解析。
- 真实 Embedding、LLM、Reranker。
- Milvus、BM25、RRF 和混合检索；这些属于阶段 4。
- 自动指数退避重试、任务取消、SSE/WebSocket 进度推送。
- 分布式事务或“失败后悄悄降级为同步执行”。

## 3. 关键选择

### 3.1 为什么使用临时 Redis 索引

阶段 2 的 `InMemoryVectorStore` 只存在于 API 进程。阶段 3 的 Worker 是另一个进程，因此它写入的内存索引无法被 API 读取。阶段 4 才引入 Milvus，所以本阶段使用 Redis 保存按文档聚合的临时索引：

```text
rag:index:{knowledge_base_id}:{document_id} → 一个文档的全部 chunks + vectors
```

Worker 每次使用 `SET` 覆盖同一个文档键，而不是追加，重试不会产生重复 chunk。阶段 4 会用 Milvus 替换这一实现；Redis 临时索引不宣称是生产级向量数据库。

### 3.2 数据库职责

`documents` 保存文档业务事实：

- 所属知识库、文件名、类型、大小。
- MinIO 原文件键和解析结果键。
- 当前状态、chunk 数量、失败原因。

`ingestion_tasks` 保存一次执行事实：

- 文档 ID、ARQ job ID。
- 状态、当前阶段、进度、错误。
- 创建、开始和结束时间。

文档表示“是什么”，任务表示“这一次处理发生了什么”。一次失败文档可以拥有多条历史任务，但同一时刻只允许一个待执行或执行中的任务。

### 3.3 状态机

任务状态：

```text
pending ──claim──> processing ──success──> completed
   │                    │
   └──enqueue error──> failed <──processing error
                           │
                           └──retry──> 新建 pending 任务
```

处理阶段：

```text
queued → parsing → chunking → embedding → indexing → completed
```

重试创建新的任务记录，保留旧任务的失败证据。Worker 使用数据库行锁认领任务；已完成、失败或正在处理的重复消息直接返回。

## 4. 一致性与补偿

跨 PostgreSQL、MinIO、Redis 的操作不能使用 SQLAlchemy 的一次 `commit()` 原子提交，因此明确每个失败点：

| 失败点 | 已产生状态 | 处理 |
|---|---|---|
| MinIO 上传失败 | 无数据库记录 | 返回 503 |
| 数据库创建失败 | MinIO 已有原文件 | 删除原文件；数据库回滚 |
| ARQ 入队失败 | 文件、文档、任务已存在 | 文档和任务标记 failed，保留文件供重试，返回 503 |
| Worker 解析/索引失败 | 文档、任务存在 | 事务回滚当前写入，再用独立事务标记 failed |
| 重复执行 | 任务已被认领或结束 | 不再处理 |
| 删除索引失败 | 文档仍存在 | 删除失败并保留业务记录，不伪装成功 |
| 删除 MinIO 失败 | 文档仍存在 | 删除失败并保留业务记录，可再次操作 |

删除顺序为“共享索引 → MinIO 对象 → PostgreSQL 记录”。只有外部资源清理成功才提交数据库删除，因此不会出现 API 报告删除成功但外部垃圾仍不可追踪的情况。

## 5. API 契约

- `POST /api/v1/knowledge-bases/{kb_id}/documents`
  - multipart 字段：`file`
  - 成功：202，返回文档与任务 ID、状态。
- `GET /api/v1/knowledge-bases/{kb_id}/documents`
- `GET /api/v1/knowledge-bases/{kb_id}/documents/{document_id}`
- `DELETE /api/v1/knowledge-bases/{kb_id}/documents/{document_id}`
- `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/retry`
- `GET /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/download`
- `GET /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/parsed`
- `GET /api/v1/ingestion-tasks/{task_id}`

统一错误继续使用：

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document not found",
    "details": null
  }
}
```

## 6. 验收标准

- [ ] 上传 `.md`/`.txt` 返回 202，接口不等待分块和索引完成。
- [ ] Worker 完成后，文档和任务均为 completed，进度为 100。
- [ ] 原文件、解析结果、数据库记录和 Redis 临时索引均可验证。
- [ ] 不支持文件返回统一 422；不存在的知识库/文档/任务返回统一 404。
- [ ] 入队或处理失败可看到明确错误，并可通过 retry 创建新任务恢复。
- [ ] 同一任务执行两次不会产生重复的可检索 chunks。
- [ ] 删除文档会清理 Redis 索引、MinIO 对象和数据库记录。
- [ ] 非空知识库删除受数据库外键约束保护。
- [ ] 单元、集成、端到端测试、Ruff 和 Pyright 全部通过。
- [ ] 学习者能口述各失败点的状态、回滚范围和补偿动作。

