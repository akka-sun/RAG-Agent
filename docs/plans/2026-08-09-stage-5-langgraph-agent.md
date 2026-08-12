# 阶段 5：LangGraph Agent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在阶段 4 混合检索基础上实现真实 LangGraph Agent，使系统能自主判断是否检索、改写查询、最多三次调用检索工具，并用真实 OpenAI-compatible Chat API 生成带证据的回答。

**Architecture:** `app/agent` 保存 Agent state、节点和图构建；`HybridRetrievalService` 作为工具被图调用；LLM 调用通过 OpenAI-compatible chat client；PostgreSQL checkpointer 使用 `langgraph-checkpoint-postgres` 并在启动或专用命令中执行 `.setup()`。

**Tech Stack:** LangGraph, langgraph-checkpoint-postgres, psycopg 3, OpenAI-compatible chat API, PostgreSQL, FastAPI, pytest, Ruff, Pyright.

## Global Constraints

- Chat LLM, Embedding, Reranker, and Langfuse are reached through real HTTP APIs configured by environment variables.
- Runtime code must never hard-code credentials.
- No hidden deterministic stand-in for the production path. Test doubles are allowed only in unit tests and marked test seams.
- The graph may call retrieval at most three times.
- The retriever remains a normal service dependency so Agent behavior can be tested without invoking paid APIs in unit tests.
- Every `Fake*` type shown in test snippets is a test-local class defined in the same test file immediately above the test, implementing only the attributes and methods asserted by that test.

---

## File Structure

- Modify `pyproject.toml`: add `langgraph`, `langgraph-checkpoint-postgres`, and `psycopg` pool/binary extras.
- Modify `.env.example`: add chat model settings if not already present.
- Modify `app/core/config.py`: expose chat and LangGraph settings.
- Create `app/infrastructure/chat_client.py`: OpenAI-compatible chat client.
- Create `app/agent/state.py`: typed Agent state and evidence contracts.
- Create `app/agent/tools.py`: retrieval tool wrapper.
- Create `app/agent/graph.py`: LangGraph graph construction and loop limit.
- Create `app/agent/checkpoint.py`: PostgreSQL checkpointer factory and setup helper.
- Create `app/services/agent_chat.py`: service entry point for one answer run.
- Modify `app/api/dependencies.py`: provide `AgentChatService`.
- Modify `app/api/routes/rag.py`: add `/rag/agent/query` or upgrade `/rag/query` according to compatibility decision.
- Add unit and integration tests.
- Update `README.md` and `docs/learning-roadmap.md`.

---

### Task 1: Agent Dependencies and Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `app/core/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `chat_base_url: str`, `chat_api_key: str`, `chat_model: str`, `agent_max_retrievals: int`, `langgraph_strict_msgpack: bool`.
- Consumes: existing settings model.

- [ ] **Step 1: Write failing settings test**

```python
def test_stage5_agent_settings(monkeypatch):
    monkeypatch.setenv("RAG_AGENT_OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("RAG_AGENT_OPENAI_API_KEY", "key")
    monkeypatch.setenv("RAG_AGENT_CHAT_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("RAG_AGENT_AGENT_MAX_RETRIEVALS", "3")

    settings = Settings()

    assert settings.chat_model == "gpt-4.1-mini"
    assert settings.agent_max_retrievals == 3
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_config.py::test_stage5_agent_settings -v`

Expected: FAIL because fields are missing.

- [ ] **Step 3: Add dependencies and settings**

Add:

```toml
"langgraph>=0.6",
"langgraph-checkpoint-postgres>=2",
"psycopg[binary,pool]>=3.2",
```

Use `RAG_AGENT_OPENAI_BASE_URL` and `RAG_AGENT_OPENAI_API_KEY` for both chat and embedding by default, while preserving separate model names.

- [ ] **Step 4: Verify settings**

Run: `uv run --no-sync pytest tests/unit/test_config.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock .env.example app/core/config.py tests/unit/test_config.py
git commit -m "feat: 配置 LangGraph Agent 依赖"
```

---

### Task 2: Chat Client

**Files:**
- Create: `app/infrastructure/chat_client.py`
- Test: `tests/unit/test_chat_client.py`
- Test: `tests/integration/test_external_chat_client.py`

**Interfaces:**
- Produces: `ChatClient.complete(messages: Sequence[ChatMessage]) -> ChatCompletionResult`.
- Consumes: OpenAI-compatible API settings.

- [ ] **Step 1: Write failing unit test**

```python
async def test_chat_client_sends_openai_compatible_messages(respx_mock):
    respx_mock.post("https://api.example.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}], "usage": {"total_tokens": 12}},
        )
    )
    client = ChatClient(base_url="https://api.example.test/v1", api_key="key", model="chat-model")

    result = await client.complete([ChatMessage(role="user", content="hello")])

    assert result.content == "answer"
    assert result.total_tokens == 12
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_chat_client.py -v`

Expected: FAIL because client does not exist.

- [ ] **Step 3: Implement client**

Use HTTP request compatible with `/chat/completions`. Normalize errors into `ExternalModelError` with service name, status code, and short message.

- [ ] **Step 4: Add guarded external test**

External test skips unless `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` and chat credentials are present.

- [ ] **Step 5: Verify local tests**

Run: `uv run --no-sync pytest tests/unit/test_chat_client.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/infrastructure/chat_client.py tests/unit/test_chat_client.py tests/integration/test_external_chat_client.py
git commit -m "feat: 接入真实 Chat API 客户端"
```

---

### Task 3: Agent State and Retrieval Tool

**Files:**
- Create: `app/agent/__init__.py`
- Create: `app/agent/state.py`
- Create: `app/agent/tools.py`
- Test: `tests/unit/test_agent_tools.py`

**Interfaces:**
- Produces: `AgentState`, `AgentEvidence`, `RetrievalTool.run(knowledge_base_id: UUID, query: str) -> list[AgentEvidence]`.
- Consumes: `HybridRetrievalService.query`.

- [ ] **Step 1: Write failing retrieval tool test**

```python
async def test_retrieval_tool_records_attempt_and_evidence():
    service = FakeRetrievalService()
    tool = RetrievalTool(service=service, limit=4)

    evidence = await tool.run(knowledge_base_id=uuid.uuid4(), query="pricing")

    assert service.queries == ["pricing"]
    assert evidence[0].label == "S1"
    assert evidence[0].text == "retrieved text"
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_agent_tools.py -v`

Expected: FAIL because `app.agent` does not exist.

- [ ] **Step 3: Implement state and tool**

State must include user query, normalized query, retrieval attempts, evidence list, final answer, and error string. Evidence labels must be stable within one run.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_agent_tools.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/agent/__init__.py app/agent/state.py app/agent/tools.py tests/unit/test_agent_tools.py
git commit -m "feat: 定义 Agent 状态与检索工具"
```

---

### Task 4: LangGraph Bounded Graph

**Files:**
- Create: `app/agent/graph.py`
- Test: `tests/unit/test_agent_graph.py`

**Interfaces:**
- Produces: `build_agent_graph(chat_client: ChatClientProtocol, retrieval_tool: RetrievalTool, max_retrievals: int) -> CompiledStateGraph`.
- Consumes: state and tool from Task 3.

- [ ] **Step 1: Write failing loop-limit test**

```python
async def test_agent_stops_after_three_retrieval_attempts():
    graph = build_agent_graph(
        chat_client=AlwaysRequestsMoreRetrievalClient(),
        retrieval_tool=FakeRetrievalTool(),
        max_retrievals=3,
    )

    result = await graph.ainvoke({"query": "hard question", "knowledge_base_id": str(uuid.uuid4())})

    assert result["retrieval_count"] == 3
    assert "insufficient evidence" in result["final_answer"].lower()
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_agent_graph.py -v`

Expected: FAIL because graph builder is missing.

- [ ] **Step 3: Implement graph**

Nodes:

```text
classify -> maybe_rewrite -> retrieve -> decide -> generate
```

The decide node routes to retrieve only when more evidence is needed and `retrieval_count < max_retrievals`.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_agent_graph.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/agent/graph.py tests/unit/test_agent_graph.py
git commit -m "feat: 实现受限 LangGraph Agent"
```

---

### Task 5: PostgreSQL Checkpointer

**Files:**
- Create: `app/agent/checkpoint.py`
- Modify: `app/main.py`
- Test: `tests/unit/test_agent_checkpoint.py`
- Test: `tests/integration/test_agent_checkpoint.py`

**Interfaces:**
- Produces: `create_async_checkpointer(database_url: str)`, `setup_checkpointer(database_url: str)`.
- Consumes: PostgreSQL database URL settings.

- [ ] **Step 1: Write failing setup test**

```python
def test_checkpointer_sets_strict_msgpack(monkeypatch):
    monkeypatch.delenv("LANGGRAPH_STRICT_MSGPACK", raising=False)

    ensure_langgraph_security_env()

    assert os.environ["LANGGRAPH_STRICT_MSGPACK"] == "true"
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_agent_checkpoint.py -v`

Expected: FAIL because checkpoint module does not exist.

- [ ] **Step 3: Implement checkpointer helper**

Use `AsyncPostgresSaver` with connection options equivalent to `autocommit=True` and `row_factory=dict_row`. Call `.setup()` from the FastAPI lifespan startup path before compiling the production graph. Set strict msgpack env before checkpointer construction.

- [ ] **Step 4: Add real integration test**

The integration test runs against test PostgreSQL, calls setup, writes a minimal checkpoint through LangGraph, and reads it back.

- [ ] **Step 5: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_agent_checkpoint.py tests/integration/test_agent_checkpoint.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/agent/checkpoint.py app/main.py tests/unit/test_agent_checkpoint.py tests/integration/test_agent_checkpoint.py
git commit -m "feat: 增加 LangGraph PostgreSQL checkpointer"
```

---

### Task 6: Agent Chat Service and API

**Files:**
- Create: `app/services/agent_chat.py`
- Modify: `app/api/dependencies.py`
- Modify: `app/api/routes/rag.py`
- Modify: `app/schemas/rag.py`
- Test: `tests/unit/test_agent_chat_service.py`
- Test: `tests/integration/test_rag_api.py`

**Interfaces:**
- Produces: `AgentChatService.answer(knowledge_base_id: UUID, query: str) -> AgentAnswer`.
- Consumes: graph builder, chat client, retrieval tool.

- [ ] **Step 1: Write failing service test**

```python
async def test_agent_chat_service_returns_answer_and_evidence():
    service = AgentChatService(graph=FakeAgentGraph())

    answer = await service.answer(knowledge_base_id=uuid.uuid4(), query="What changed?")

    assert answer.content == "final answer"
    assert answer.citations[0].label == "S1"
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_agent_chat_service.py -v`

Expected: FAIL because service is missing.

- [ ] **Step 3: Implement service and route**

Add `POST /api/v1/rag/agent/query` with knowledge base ID, query, and optional max results. Keep Stage 4 retrieval endpoint available for debugging.

- [ ] **Step 4: Verify API tests**

Run: `uv run --no-sync pytest tests/unit/test_agent_chat_service.py tests/integration/test_rag_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/services/agent_chat.py app/api/dependencies.py app/api/routes/rag.py app/schemas/rag.py tests/unit/test_agent_chat_service.py tests/integration/test_rag_api.py
git commit -m "feat: 暴露 Agent 查询 API"
```

---

### Task 7: Stage 5 Documentation and Acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`
- Create: `docs/plans/2026-08-09-stage-5-progress.md`

**Interfaces:**
- Consumes: Tasks 1-6 verification outputs.
- Produces: documented Agent API and learning review.

- [ ] **Step 1: Update README**

Document Agent endpoint, chat API env vars, retrieval loop limit, and checkpointer setup.

- [ ] **Step 2: Update roadmap**

Add Stage 5 completion record and questions covering state, retrieval choices, and loop limits.

- [ ] **Step 3: Run final gates**

Run:

```powershell
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
```

Expected: PASS without external tests. External Chat API verification runs only with configured credentials.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/learning-roadmap.md docs/plans/2026-08-09-stage-5-progress.md
git commit -m "docs: 完成阶段五 Agent 验收记录"
```
