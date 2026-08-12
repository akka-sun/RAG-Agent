# 阶段 6 进度记录：会话、SSE 与引用

日期：2026-08-09

## 已完成范围

- 新增 `conversations`、`messages`、`message_citations` ORM 模型与 Alembic 迁移。
- 新增 `messages.sequence_number` 数据库序号，避免同一事务内 `created_at` 相同导致消息顺序不稳定。
- 新增 Conversation 与 Message Repository，覆盖会话创建、列表、查询、删除、消息写入、引用写入和非法引用拒绝。
- 新增 Conversation Service 与 Pydantic schema，处理知识库存在性校验、标题清洗、消息与引用响应序列化。
- 新增会话 REST API：
  - `POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations`
  - `GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations`
  - `GET /api/v1/conversations/{conversation_id}`
  - `DELETE /api/v1/conversations/{conversation_id}`
  - `GET /api/v1/conversations/{conversation_id}/messages`
- 新增 SSE 事件 schema 与格式化函数，事件名固定为 `message_start`、`agent_status`、`retrieval_start`、`retrieval_result`、`token`、`citation`、`message_end`、`error`。
- 新增 `SSEChatService`，在流式请求中保存用户消息、调用 Stage 5 Agent、输出 token/citation 事件，并将 assistant message 与引用快照同事务落库。
- 新增 `POST /api/v1/conversations/{conversation_id}/messages/stream`，返回 `text/event-stream`。
- 更新 README 与学习路线图，说明会话、SSE、引用快照和当前后续阶段。

## 真实外部服务边界

- PostgreSQL：Docker Compose 中保存知识库、文档、摄取任务、会话、消息、引用和 LangGraph checkpoint。
- Redis：Docker Compose 中继续承载 ARQ 队列。
- MinIO：Docker Compose 中保存原文和解析结果。
- Milvus：Docker Compose 中保存生产级文档分块索引。
- Chat / Embedding / Reranker：通过 OpenAI-compatible HTTP API 配置；当前环境未提供真实凭据时，`external` 测试按设计跳过，避免误消耗额度。

## 已验证行为

- 会话必须归属已存在知识库；缺失知识库返回统一 404。
- 会话标题会去除首尾空白，空标题会被校验拒绝。
- 删除会话会级联删除业务消息与引用快照，但不会删除知识库或文档。
- assistant citation 在落库前校验 source label，非法引用不会留下部分消息。
- SSE 接口会输出开始、状态、token、citation 和结束事件。
- SSE 接口完成后可通过消息列表恢复 user/assistant 消息与引用快照。
- 同一事务内 user/assistant 消息拥有相同 `created_at` 时，读取仍按数据库插入序号返回。

## 验收命令

阶段 6 局部门禁已通过：

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_conversation_models.py -v
docker compose exec api uv run --no-sync pytest tests/integration/test_conversation_repositories.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_conversation_schemas.py tests/unit/test_conversation_service.py -v
docker compose exec api uv run --no-sync pytest tests/integration/test_conversations_api.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_sse_chat.py -v
docker compose exec api uv run --no-sync pytest tests/integration/test_chat_sse_api.py -v
```

阶段 6 全量门禁已通过：

```powershell
docker compose config --quiet
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec -e RAG_AGENT_POSTGRES_DB=rag_agent_test api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
docker compose exec api uv run --no-sync pytest -m external -v
```

实际结果：

- `docker compose config --quiet`：通过
- `alembic upgrade head`：主库与测试库均升级到 `20260809_0005`
- `ruff format --check .`：148 files already formatted
- `ruff check .`：All checks passed
- `pyright`：0 errors, 0 warnings, 0 informations
- `tests/unit`：133 passed, 1 warning
- `tests/integration`：43 passed, 3 skipped
- `tests/e2e`：1 passed
- `pytest -m external`：3 skipped, 177 deselected；当前环境未配置真实外部模型凭据，入口已就绪

## 后续进入阶段 7

- 在上传校验中支持 PDF。
- 通过 Docker Compose 配置 MinerU 与 PaddleX 服务。
- 增加解析器选择参数，不在 MinerU 与 PaddleX 之间静默 fallback。
- 将 Markdown/TXT 和 PDF 统一归一化为 `ParsedDocument`。
- 将 PDF 页码、章节、OCR 坐标等元数据传递到 chunk、Milvus 和 citation。
