# 阶段 8：工程质量与可观测性实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可诊断、可追踪、可复现的生产质量门槛，使摄取、解析、检索、Agent、SSE 和外部 API 调用都能通过日志与 Langfuse trace 定位失败阶段。

**Architecture:** 使用请求/任务级 trace context 贯穿 API、Worker、Parser、Embedding、Milvus、Reranker、Agent 和 SSE；结构化日志输出稳定字段；Langfuse 在配置完整时启用，未配置时不影响主链路；全仓格式、Lint、类型、迁移、单元、集成、E2E 和外部测试分层明确。

**Tech Stack:** Python logging, contextvars, Langfuse Python SDK, FastAPI middleware, pytest markers, Docker Compose, Ruff, Pyright, Alembic.

## Global Constraints

- Logs always include trace ID and stage. Logs also include knowledge base ID, document ID, task ID, conversation ID, message ID, parser, and retrieval attempt when that value exists in the current request, worker task, or service call.
- Missing Langfuse configuration disables trace export without breaking the request.
- Default local checks must avoid accidentally spending paid API quota; explicit external verification commands exercise real APIs.
- `ruff format --check .`, `ruff check .`, `pyright`, Alembic migration, unit, integration, and E2E gates must pass before claiming completion.

---

## File Structure

- Create `app/observability/context.py`: trace contextvars and helpers.
- Create `app/observability/logging.py`: JSON-style structured logging setup.
- Create `app/observability/langfuse.py`: optional Langfuse client and span helpers.
- Modify `app/main.py`: middleware and startup logging setup.
- Modify `app/worker.py`: worker trace setup.
- Modify service modules to attach trace fields.
- Modify `pyproject.toml`: ensure pytest markers and Ruff format include docs.
- Add `tests/unit/test_observability.py`.
- Add `tests/integration/test_observability.py`.
- Add `tests/integration/test_external_tracing.py`.
- Modify `README.md`, `docs/learning-roadmap.md`, and create progress doc.

---

### Task 1: Full-Repository Formatting Gate

**Files:**
- Modify: files currently failing `ruff format --check .`
- Test: command verification only

**Interfaces:**
- Produces: full repository format gate that passes.
- Consumes: current Ruff configuration.

- [ ] **Step 1: Reproduce formatting failure**

Run: `uv run --no-sync ruff format --check .`

Expected: FAIL on currently unformatted migration/doc files or line ending inconsistencies.

- [ ] **Step 2: Apply formatting**

Run: `uv run --no-sync ruff format .`

Expected: Ruff formats only files it owns. Review diff carefully to ensure no semantic changes.

- [ ] **Step 3: Verify full format gate**

Run: `uv run --no-sync ruff format --check .`

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add .
git commit -m "style: 统一全仓 Ruff 格式"
```

---

### Task 2: Trace Context and Structured Logging

**Files:**
- Create: `app/observability/__init__.py`
- Create: `app/observability/context.py`
- Create: `app/observability/logging.py`
- Modify: `app/main.py`
- Test: `tests/unit/test_observability.py`

**Interfaces:**
- Produces: `TraceContext`, `set_trace_context`, `get_trace_context`, `clear_trace_context`, `configure_logging`.
- Consumes: FastAPI request lifecycle and Python logging.

- [ ] **Step 1: Write failing context test**

```python
def test_trace_context_round_trip():
    token = set_trace_context(trace_id="trace-1", knowledge_base_id="kb-1")

    assert get_trace_context().trace_id == "trace-1"
    assert get_trace_context().knowledge_base_id == "kb-1"

    clear_trace_context(token)
    assert get_trace_context().trace_id is None
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_observability.py -v`

Expected: FAIL because observability module is missing.

- [ ] **Step 3: Implement context and logging**

Use `contextvars` for trace context. Logging formatter must include stable keys: `trace_id`, `stage`, `knowledge_base_id`, `document_id`, `task_id`, `conversation_id`, and `message_id` when set.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_observability.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/observability/__init__.py app/observability/context.py app/observability/logging.py app/main.py tests/unit/test_observability.py
git commit -m "feat: 增加 trace context 与结构化日志"
```

---

### Task 3: Instrument API, Worker, and Services

**Files:**
- Modify: `app/main.py`
- Modify: `app/worker.py`
- Modify: `app/services/ingestion.py`
- Modify: `app/services/retrieval.py`
- Modify: `app/services/agent_chat.py`
- Modify: `app/services/sse_chat.py`
- Test: `tests/integration/test_observability.py`

**Interfaces:**
- Consumes: trace context from Task 2.
- Produces: trace ID propagation through HTTP and worker flows.

- [ ] **Step 1: Write failing integration test**

```python
async def test_http_trace_id_is_returned_and_logged(async_client, caplog):
    response = await async_client.get("/api/v1/health/live", headers={"x-trace-id": "trace-test"})

    assert response.headers["x-trace-id"] == "trace-test"
    assert any("trace-test" in record.getMessage() for record in caplog.records)
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/integration/test_observability.py -v`

Expected: FAIL because middleware does not propagate trace ID.

- [ ] **Step 3: Implement instrumentation**

Middleware reads `x-trace-id` or generates one. Worker creates trace ID per task. Service stages log start, success, and failure with stage names: `upload`, `parse`, `chunk`, `embed`, `index`, `retrieve`, `rerank`, `agent`, `sse`.

- [ ] **Step 4: Verify instrumentation**

Run: `uv run --no-sync pytest tests/integration/test_observability.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/main.py app/worker.py app/services/ingestion.py app/services/retrieval.py app/services/agent_chat.py app/services/sse_chat.py tests/integration/test_observability.py
git commit -m "feat: 为 API Worker 与核心链路增加追踪日志"
```

---

### Task 4: Optional Langfuse Tracing

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `app/core/config.py`
- Create: `app/observability/langfuse.py`
- Test: `tests/unit/test_langfuse_observability.py`
- Test: `tests/integration/test_external_tracing.py`

**Interfaces:**
- Produces: `LangfuseTracer.enabled`, `span(name: str, metadata: dict[str, object])`.
- Consumes: Langfuse base URL and keys.

- [ ] **Step 1: Write failing disabled-mode test**

```python
def test_langfuse_tracer_is_disabled_without_keys():
    tracer = LangfuseTracer(base_url="", public_key="", secret_key="")

    assert tracer.enabled is False
    with tracer.span("retrieve", {"document_id": "d1"}):
        assert True
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_langfuse_observability.py -v`

Expected: FAIL because tracer does not exist.

- [ ] **Step 3: Implement optional tracer**

Add `langfuse>=4,<5`. If any required setting is absent, tracer is disabled. If enabled, create spans around external model calls, retrieval, parser calls, and SSE completion.

- [ ] **Step 4: Add external tracing test**

Skip unless `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` and Langfuse credentials exist. Test sends one trace and flushes client.

- [ ] **Step 5: Verify local tests**

Run: `uv run --no-sync pytest tests/unit/test_langfuse_observability.py -v`

Expected: PASS without credentials.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml uv.lock .env.example app/core/config.py app/observability/langfuse.py tests/unit/test_langfuse_observability.py tests/integration/test_external_tracing.py
git commit -m "feat: 增加可选 Langfuse Trace"
```

---

### Task 5: Test Marker and External Gate Cleanup

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/conftest.py` if present or create shared test guard.
- Test: `tests/unit/test_external_test_guards.py`

**Interfaces:**
- Produces: `requires_external_services()` pytest helper or marker behavior.
- Consumes: `RAG_AGENT_EXTERNAL_TESTS_ENABLED`.

- [ ] **Step 1: Write failing guard test**

```python
def test_external_guard_skips_when_disabled(monkeypatch):
    monkeypatch.delenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", raising=False)

    assert external_tests_enabled() is False
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_external_test_guards.py -v`

Expected: FAIL because guard helper is missing.

- [ ] **Step 3: Implement guard**

All tests marked `external` must skip unless enabled. The skip reason must name the required env var.

- [ ] **Step 4: Verify marker behavior**

Run:

```powershell
uv run --no-sync pytest -m external -v
uv run --no-sync pytest -m "not external" tests/unit -v
```

Expected: external tests skip without credentials; non-external tests pass.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml tests/conftest.py tests/unit/test_external_test_guards.py
git commit -m "test: 统一真实外部服务测试门禁"
```

---

### Task 6: Stage 8 Documentation and Acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`
- Create: `docs/plans/2026-08-09-stage-8-progress.md`

**Interfaces:**
- Consumes: Tasks 1-5 verification outputs.
- Produces: documented quality and observability playbook.

- [ ] **Step 1: Update README**

Document logging fields, trace header, Langfuse env vars, default test gates, and external test command.

- [ ] **Step 2: Update roadmap**

Add Stage 8 completion record and review questions about testing boundaries and trace diagnosis.

- [ ] **Step 3: Run final gates**

Run:

```powershell
docker compose config --quiet
docker compose exec api uv run --no-sync alembic current --check-heads
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
```

Expected: PASS. External tests require explicit env and credentials.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/learning-roadmap.md docs/plans/2026-08-09-stage-8-progress.md
git commit -m "docs: 完成阶段八质量与可观测性验收记录"
```
