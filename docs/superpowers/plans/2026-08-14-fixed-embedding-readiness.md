# Fixed Embedding and Readiness Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make embedding configuration server-owned and expose real PostgreSQL, Redis, MinIO, and Milvus readiness in the status page.

**Architecture:** `Settings` remains the single source of truth for embedding model and dimension; the knowledge-base service injects those values into persisted records. A focused readiness service runs four independent bounded probes and returns sanitized per-service results through `/api/v1/health/ready`; the Vue status page consumes only that API.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async, redis/arq, MinIO Python SDK, pymilvus, pytest, Vue 3, TypeScript, Pinia, Vitest.

## Global Constraints

- Keep `GET /api/v1/health/live` as a dependency-free liveness endpoint.
- `GET /api/v1/health/ready` returns HTTP 200 with top-level `ok` or `degraded` when probes execute.
- Never expose credentials, connection strings, tokens, hostnames, raw exceptions, or tracebacks.
- Knowledge-base responses retain read-only `embedding_model` and `embedding_dimension`.
- Do not support per-knowledge-base embedding selection or index migration.
- Every production behavior starts with a test that fails for the expected missing behavior.

---

### Task 1: Make embedding configuration server-owned

**Files:**
- Modify: `app/schemas/knowledge_base.py`
- Modify: `app/services/knowledge_base.py`
- Modify: `app/api/dependencies.py`
- Modify: `tests/unit/test_knowledge_base_service.py`
- Modify: `tests/integration/test_knowledge_bases_api.py`

**Interfaces:**
- Consumes: `Settings.embedding_model: str`, `Settings.embedding_dimension: int`.
- Produces: `KnowledgeBaseCreate(name: str, description: str = "")` and `KnowledgeBaseService(..., embedding_model: str, embedding_dimension: int)`.

- [ ] **Step 1: Write failing schema and service tests**

Add tests proving the request model rejects client-supplied embedding fields and the service persists configured values:

```python
payload = KnowledgeBaseCreate.model_validate({"name": "产品文档", "description": ""})
item = await KnowledgeBaseService(
    repository,
    session,
    embedding_model="Qwen/Qwen3-Embedding-8B",
    embedding_dimension=4096,
).create(payload)
assert item.embedding_model == "Qwen/Qwen3-Embedding-8B"
assert item.embedding_dimension == 4096

with pytest.raises(ValidationError):
    KnowledgeBaseCreate.model_validate({
        "name": "越权配置",
        "embedding_model": "other",
        "embedding_dimension": 12,
    })
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/test_knowledge_base_service.py tests/integration/test_knowledge_bases_api.py -q`

Expected: failures show the create schema still requires/accepts embedding fields and the service lacks configuration injection.

- [ ] **Step 3: Implement the minimal server-owned contract**

Set `model_config = ConfigDict(extra="forbid")` on `KnowledgeBaseCreate`, retain only name and description, inject settings in `get_knowledge_base_service`, and construct the ORM entity explicitly:

```python
item = KnowledgeBase(
    name=data.name,
    description=data.description,
    embedding_model=self._embedding_model,
    embedding_dimension=self._embedding_dimension,
)
```

- [ ] **Step 4: Update integration payloads and verify GREEN**

Use `{ "name": ..., "description": ... }` for successful requests and assert extra embedding fields return unified HTTP 422 validation errors. Re-run the focused command and require all tests to pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add app/schemas/knowledge_base.py app/services/knowledge_base.py app/api/dependencies.py tests/unit/test_knowledge_base_service.py tests/integration/test_knowledge_bases_api.py
git commit -m "fix(api): own knowledge base embedding config"
```

---

### Task 2: Add bounded dependency readiness probes

**Files:**
- Create: `app/services/readiness.py`
- Create: `app/schemas/health.py`
- Modify: `app/api/dependencies.py`
- Modify: `app/main.py`
- Create: `tests/unit/test_readiness.py`
- Modify: `tests/unit/test_health.py`

**Interfaces:**
- Produces: `ReadinessService.check() -> ReadinessResponse`.
- Produces: `GET /api/v1/health/ready` returning `{status, services}`.
- Probe protocol: each injected async callable returns `None` on success and raises on failure.

- [ ] **Step 1: Write failing readiness service tests**

Cover concurrent success, one failure without suppressing peers, timeout, latency, and sanitized errors:

```python
result = await service.check()
assert result.status == "degraded"
assert result.services["postgresql"].status == "healthy"
assert result.services["redis"].status == "unhealthy"
assert result.services["redis"].error == "Redis 连接失败"
assert "redis://" not in result.model_dump_json()
```

Use events in fake probes to prove all four start before any one finishes; use a very small injected timeout for the timeout case.

- [ ] **Step 2: Run service tests and verify RED**

Run: `uv run pytest tests/unit/test_readiness.py -q`

Expected: import failure because `app.services.readiness` does not exist.

- [ ] **Step 3: Implement schemas and orchestration**

Define literal status models and use `asyncio.gather` plus `asyncio.wait_for` per probe. Convert every exception to a fixed service-specific Chinese message; measure latency with `time.perf_counter` and never serialize exception text.

- [ ] **Step 4: Write failing endpoint tests**

Override a `get_readiness_service` dependency with a fake and assert `/api/v1/health/ready` returns the exact response shape while `/health/live` remains unchanged.

- [ ] **Step 5: Implement real probes and endpoint**

Implement:

```python
await session.execute(text("SELECT 1"))
await redis.ping()
await asyncio.to_thread(minio.bucket_exists, settings.minio_bucket)
await asyncio.to_thread(milvus.has_collection, settings.milvus_collection)
```

Create and close probe-scoped Redis/Milvus resources. Reuse the request-scoped SQLAlchemy session and configured MinIO client. The Milvus probe checks only and must not call `ensure_collection`.

- [ ] **Step 6: Verify Task 2 GREEN**

Run: `uv run pytest tests/unit/test_readiness.py tests/unit/test_health.py -q`

Then run: `uv run pytest tests/unit -q`

- [ ] **Step 7: Commit Task 2**

```powershell
git add app/services/readiness.py app/schemas/health.py app/api/dependencies.py app/main.py tests/unit/test_readiness.py tests/unit/test_health.py
git commit -m "feat(api): expose infrastructure readiness"
```

---

### Task 3: Simplify knowledge-base creation UI

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/components/knowledge-base/KnowledgeBaseForm.vue`
- Create: `frontend/src/components/knowledge-base/KnowledgeBaseForm.spec.ts`
- Modify: `frontend/src/stores/knowledge-bases.spec.ts`
- Modify: `frontend/e2e/fixtures.ts`

**Interfaces:**
- Produces: frontend `KnowledgeBaseCreate` with only `name` and `description`.
- Preserves response `KnowledgeBase.embedding_model` and `.embedding_dimension`.

- [ ] **Step 1: Write failing form test**

Mount the real form, assert model/dimension inputs are absent, fill name and description, submit, and assert:

```ts
expect(wrapper.emitted('submit')?.[0]).toEqual([{
  name: '产品知识库',
  description: '产品资料',
}])
```

- [ ] **Step 2: Run focused frontend tests and verify RED**

Run: `pnpm test:run src/components/knowledge-base/KnowledgeBaseForm.spec.ts src/stores/knowledge-bases.spec.ts`

Expected: the form still renders and requires embedding fields.

- [ ] **Step 3: Implement minimal form and type changes**

Remove embedding form state, validation, controls, and emitted fields. Update the E2E fixture create handler to fill the response model/dimension from fixed fixture configuration rather than request data.

- [ ] **Step 4: Verify Task 3 GREEN**

Run the focused command and require all tests to pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add frontend/src/types/api.ts frontend/src/components/knowledge-base/KnowledgeBaseForm.vue frontend/src/components/knowledge-base/KnowledgeBaseForm.spec.ts frontend/src/stores/knowledge-bases.spec.ts frontend/e2e/fixtures.ts
git commit -m "fix(frontend): simplify knowledge base creation"
```

---

### Task 4: Render real infrastructure readiness

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/resources.ts`
- Modify: `frontend/src/api/resources.spec.ts`
- Modify: `frontend/src/pages/StatusPage.vue`
- Modify: `frontend/src/pages/StatusPage.spec.ts`
- Modify: `frontend/e2e/fixtures.ts`
- Modify: `frontend/e2e/rag-workflow.spec.ts`

**Interfaces:**
- Consumes: `healthApi.ready(signal?) -> ReadinessResponse`.
- Displays exactly four service keys: `postgresql`, `redis`, `minio`, `milvus`.

- [ ] **Step 1: Write failing API and page tests**

Add a resource test for `/api/v1/health/ready`. Update the status page tests to resolve `live` and `ready` concurrently and assert healthy cards with latency, a mixed degraded response, an unreachable readiness response shown as “无法检测”, one combined retry, no overlapping checks, and stale response isolation.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pnpm test:run src/api/resources.spec.ts src/pages/StatusPage.spec.ts`

Expected: `healthApi.ready` is missing and infrastructure remains hard-coded as unsupported.

- [ ] **Step 3: Implement readiness types, client, and page state**

Add:

```ts
export type ServiceReadiness = {
  status: 'healthy' | 'unhealthy'
  latency_ms: number
  error?: string | null
}
export type ReadinessResponse = {
  status: 'ok' | 'degraded'
  services: Record<'postgresql' | 'redis' | 'minio' | 'milvus', ServiceReadiness>
}
```

Run live and ready with `Promise.allSettled`, retain independent results, render accessible status text, and preserve the existing generation and busy guards.

- [ ] **Step 4: Update E2E contract fixtures and assertions**

Mock the exact ready endpoint with four healthy services and assert the status journey shows all four by name and healthy state. Keep the cross-origin guard and unknown-route failure behavior.

- [ ] **Step 5: Verify Task 4 GREEN**

Run focused tests, then:

```powershell
pnpm test:run
pnpm typecheck
pnpm build
pnpm test:e2e
```

- [ ] **Step 6: Commit Task 4**

```powershell
git add frontend/src/types/api.ts frontend/src/api/resources.ts frontend/src/api/resources.spec.ts frontend/src/pages/StatusPage.vue frontend/src/pages/StatusPage.spec.ts frontend/e2e/fixtures.ts frontend/e2e/rag-workflow.spec.ts
git commit -m "feat(frontend): show infrastructure readiness"
```

---

### Task 5: Real Compose verification and documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Verifies the public same-origin endpoints at port `5173`.

- [ ] **Step 1: Rebuild and start the changed services**

Run: `docker compose -p rag-agent up -d --build api worker frontend`

- [ ] **Step 2: Verify real response contract**

Run requests to `/api/v1/health/live` and `/api/v1/health/ready`. Require HTTP 200, top-level `ok`, and all four services `healthy`. Confirm `docker compose -p rag-agent ps` reports API, worker dependencies, and frontend healthy.

- [ ] **Step 3: Verify real knowledge-base creation**

POST only `name` and `description`, assert the response contains the configured global model and dimension, then delete the verification knowledge base through the API.

- [ ] **Step 4: Document behavior and commands**

Update README to state that embedding configuration is global and to explain the difference between liveness and readiness endpoints without exposing secrets.

- [ ] **Step 5: Run final gates and commit**

Run backend tests relevant to changed contracts, frontend full tests/typecheck/build/E2E, `docker compose config --quiet`, `git diff --check`, and secret scan of the changed range.

```powershell
git add README.md
git commit -m "docs: explain embedding and readiness status"
```
