# 阶段 5 进度记录：LangGraph Agent

日期：2026-08-09

## 已完成范围

- 增加 LangGraph、langgraph-checkpoint-postgres 与 psycopg 依赖。
- 增加 Chat API 配置：`RAG_AGENT_CHAT_BASE_URL`、`RAG_AGENT_CHAT_API_KEY`、`RAG_AGENT_CHAT_MODEL`、`RAG_AGENT_AGENT_MAX_RETRIEVALS`、`RAG_AGENT_LANGGRAPH_STRICT_MSGPACK`。
- 实现 OpenAI-compatible `ChatClient`，支持 `/chat/completions`、Bearer 鉴权、usage 解析和 HTTP 错误归一化。
- 实现 Agent 状态、引用证据结构和检索工具封装。
- 实现 LangGraph Agent 图：
  - `classify`：判断是否需要检索。
  - `maybe_rewrite`：将用户问题改写为检索查询。
  - `retrieve`：调用 Stage 4 混合检索工具。
  - `decide`：判断证据是否足够。
  - `generate`：生成最终回答或在达到上限后返回证据不足。
- 实现 PostgreSQL checkpointer helper，并在 FastAPI lifespan 启动阶段执行 setup。
- 实现 `AgentChatService` 与 `POST /api/v1/rag/agent/query`。
- 保留 `/api/v1/rag/query` 作为 Stage 4 混合检索调试入口。

## 真实外部服务边界

- Milvus：Docker Compose 中运行 `milvus-etcd`、`milvus-minio`、`milvus-standalone`。
- PostgreSQL：业务状态与 LangGraph checkpoint 使用 Docker PostgreSQL。
- MinIO：业务对象存储使用 Docker MinIO。
- Redis：ARQ 队列使用 Docker Redis。
- Chat / Embedding / Reranker：通过 OpenAI-compatible HTTP API 配置；真实外部 API 测试默认跳过，需显式设置 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 和真实凭据。

## 已验证行为

- ChatClient 会发送 OpenAI-compatible payload，并解析 `choices[0].message.content` 与 `usage.total_tokens`。
- ChatClient 对 HTTP 错误返回 `ExternalModelError`，携带服务名、状态码和短错误信息。
- Agent 可在分类为 `DIRECT` 时直接生成回答，不调用检索工具。
- Agent 在模型持续返回 `NEED_MORE` 时最多检索三次，并返回 `Insufficient evidence...`。
- Checkpointer 会设置 `LANGGRAPH_STRICT_MSGPACK=true`。
- Checkpointer 可在真实测试 PostgreSQL 中 setup、写入并读回 checkpoint。
- `/rag/agent/query` 会先校验知识库，再返回回答和引用列表。

## 验收命令

阶段 5 局部门禁已通过：

```powershell
docker compose exec api uv run --no-sync pytest tests/unit/test_chat_client.py tests/integration/test_external_chat_client.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_agent_tools.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_agent_graph.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_agent_checkpoint.py tests/integration/test_agent_checkpoint.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_agent_chat_service.py tests/integration/test_rag_api.py -v
```

阶段 5 全量门禁已通过：

```powershell
docker compose config --quiet
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
docker compose exec api uv run --no-sync pytest -m external -v
```

实际结果：

- `ruff format --check .`：128 files already formatted
- `ruff check .`：All checks passed
- `pyright`：0 errors, 0 warnings, 0 informations
- `tests/unit`：124 passed, 1 warning
- `tests/integration`：34 passed, 3 skipped
- `tests/e2e`：1 passed
- `pytest -m external`：3 skipped, 159 deselected；当前环境未配置真实外部模型凭据，入口已就绪

## 后续进入阶段 6

- 增加会话和消息表。
- 让 Agent 使用稳定 thread/session，而不是每次请求创建临时 thread。
- 增加 SSE 流式 endpoint，输出 Agent 状态、检索事件、token 和引用。
- 将引用快照持久化，确保刷新后可恢复。
