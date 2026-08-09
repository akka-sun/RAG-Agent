# 阶段 4：Milvus 混合检索实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将阶段 3 的 Redis 临时文档索引升级为真实 Milvus 检索存储，并实现 Dense、BM25、RRF、去重和真实 Reranker API 的生产查询链路。

**Architecture:** Worker 在摄取完成前把 chunk、dense vector、BM25 文本字段和引用元数据写入 Milvus；API 查询通过 `HybridRetrievalService` 执行 Milvus 双路召回、RRF 融合、去重和远程 Reranker。Redis 只保留 ARQ 队列职责，不再作为生产检索索引。

**Tech Stack:** FastAPI, SQLAlchemy async, ARQ, MinIO, Redis, Milvus standalone Docker service, PyMilvus, OpenAI-compatible Embedding API, external Reranker API, pytest, Ruff, Pyright.

## Global Constraints

- Milvus runs as a real Docker Compose service.
- Chat LLM, Embedding, Reranker, and Langfuse are reached through real HTTP APIs configured by environment variables.
- Default local checks must avoid accidentally spending paid API quota; explicit external verification commands exercise real APIs.
- Runtime code must never hard-code credentials.
- No hidden deterministic stand-in for the production path. Test doubles are allowed only in unit tests and marked test seams.
- Knowledge base isolation must be enforced on every insert, search, retry cleanup, and delete cleanup path.
- Every `Fake*` type shown in test snippets is a test-local class defined in the same test file immediately above the test, implementing only the attributes and methods asserted by that test.

---

## File Structure

- Modify `pyproject.toml`: add `pymilvus`, `openai`, and HTTP dependencies if missing.
- Modify `docker-compose.yml`: add Milvus standalone and its supporting services or official standalone compose-compatible services.
- Modify `.env.example`: add Milvus, Embedding, and Reranker settings.
- Modify `app/core/config.py`: expose strongly typed Milvus/model/reranker settings.
- Create `app/rag/hybrid.py`: pure ranking types, RRF, dedupe, and result contracts.
- Create `app/infrastructure/milvus_store.py`: Milvus collection management, insert, search, delete.
- Create `app/infrastructure/model_clients.py`: OpenAI-compatible embedding client and reranker client.
- Create `app/services/retrieval.py`: orchestration service for query embedding, Milvus retrieval, RRF, dedupe, rerank.
- Modify `app/services/ingestion.py`: write completed chunks into Milvus instead of Redis production index.
- Modify `app/services/documents.py`: delete and retry must clean Milvus chunks.
- Modify `app/api/dependencies.py`: provide retrieval and Milvus dependencies.
- Modify `app/api/routes/rag.py`: route `/rag/query` to the hybrid retrieval service while keeping request/response compatibility where possible.
- Add tests under `tests/unit/` and `tests/integration/`.
- Update `README.md` and `docs/learning-roadmap.md` with Stage 4 status and commands.

---

### Task 1: Configuration and Docker Milvus

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `app/core/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: settings fields `milvus_uri: str`, `milvus_token: str | None`, `milvus_collection: str`, `embedding_base_url: str`, `embedding_api_key: str`, `embedding_model: str`, `embedding_dimension: int`, `rerank_base_url: str`, `rerank_api_key: str`, `rerank_model: str`.
- Consumes: existing `Settings` model and `.env.example` conventions.

- [ ] **Step 1: Write failing config test**

```python
def test_stage4_external_service_settings(monkeypatch):
    monkeypatch.setenv("RAG_AGENT_MILVUS_URI", "http://milvus:19530")
    monkeypatch.setenv("RAG_AGENT_MILVUS_COLLECTION", "rag_chunks")
    monkeypatch.setenv("RAG_AGENT_OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("RAG_AGENT_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("RAG_AGENT_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("RAG_AGENT_EMBEDDING_DIMENSION", "1536")
    monkeypatch.setenv("RAG_AGENT_RERANK_BASE_URL", "https://rerank.example.test")
    monkeypatch.setenv("RAG_AGENT_RERANK_API_KEY", "rerank-key")
    monkeypatch.setenv("RAG_AGENT_RERANK_MODEL", "bge-reranker-v2")

    settings = Settings()

    assert settings.milvus_uri == "http://milvus:19530"
    assert settings.embedding_dimension == 1536
    assert settings.rerank_model == "bge-reranker-v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/unit/test_config.py::test_stage4_external_service_settings -v`

Expected: FAIL because the new settings fields do not exist.

- [ ] **Step 3: Add dependencies and settings**

Add project dependencies:

```toml
"httpx>=0.28",
"openai>=1.0",
"pymilvus>=2.6,<3",
```

Add typed settings with defaults that are safe for Docker local development:

```python
milvus_uri: str = "http://milvus:19530"
milvus_token: str | None = None
milvus_collection: str = "rag_chunks"
embedding_base_url: str = "https://api.openai.com/v1"
embedding_api_key: str = ""
embedding_model: str = "text-embedding-3-small"
embedding_dimension: int = 1536
rerank_base_url: str = ""
rerank_api_key: str = ""
rerank_model: str = ""
```

- [ ] **Step 4: Add Docker Compose services**

Use official Milvus standalone Docker Compose shape: Milvus standalone with its required etcd and object storage services. Expose `19530` to the internal Compose network and optionally to localhost through `RAG_AGENT_MILVUS_EXPOSED_PORT`.

- [ ] **Step 5: Verify config and compose**

Run:

```powershell
uv run --no-sync pytest tests/unit/test_config.py -v
docker compose config --quiet
```

Expected: config tests pass and Compose validates.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml uv.lock .env.example docker-compose.yml app/core/config.py tests/unit/test_config.py
git commit -m "feat: 配置 Milvus 与外部检索服务"
```

---

### Task 2: Pure Hybrid Ranking Contracts

**Files:**
- Create: `app/rag/hybrid.py`
- Test: `tests/unit/test_hybrid_retrieval.py`

**Interfaces:**
- Produces: `RetrievedChunk`, `RankedChunk`, `rrf_score(rank: int, k: int = 60) -> float`, `fuse_rrf(dense: Sequence[RetrievedChunk], sparse: Sequence[RetrievedChunk], limit: int) -> list[RankedChunk]`, `dedupe_chunks(chunks: Sequence[RankedChunk]) -> list[RankedChunk]`.
- Consumes: no infrastructure clients.

- [ ] **Step 1: Write failing RRF and dedupe tests**

```python
def test_fuse_rrf_prefers_chunk_present_in_both_paths():
    dense = [
        RetrievedChunk(
            chunk_id="a", document_id="d1", text="dense a", rank=1, score=0.9, source="dense"
        ),
        RetrievedChunk(
            chunk_id="b", document_id="d1", text="dense b", rank=2, score=0.8, source="dense"
        ),
    ]
    sparse = [
        RetrievedChunk(
            chunk_id="b", document_id="d1", text="sparse b", rank=1, score=12.0, source="sparse"
        ),
        RetrievedChunk(
            chunk_id="c", document_id="d1", text="sparse c", rank=2, score=8.0, source="sparse"
        ),
    ]

    fused = fuse_rrf(dense, sparse, limit=3)

    assert [item.chunk_id for item in fused] == ["b", "a", "c"]
    assert fused[0].dense_rank == 2
    assert fused[0].sparse_rank == 1


def test_dedupe_chunks_keeps_highest_ranked_chunk():
    chunks = [
        RankedChunk(chunk_id="a", document_id="d1", text="first", rrf_score=0.03),
        RankedChunk(chunk_id="a", document_id="d1", text="second", rrf_score=0.01),
    ]

    assert dedupe_chunks(chunks)[0].text == "first"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run --no-sync pytest tests/unit/test_hybrid_retrieval.py -v`

Expected: FAIL because `app.rag.hybrid` does not exist.

- [ ] **Step 3: Implement pure ranking module**

Implement frozen dataclasses or Pydantic models with explicit fields. RRF must use `1 / (k + rank)` and must not add raw dense and sparse scores.

- [ ] **Step 4: Verify pure tests**

Run: `uv run --no-sync pytest tests/unit/test_hybrid_retrieval.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/rag/hybrid.py tests/unit/test_hybrid_retrieval.py
git commit -m "feat: 实现 RRF 融合与检索结果去重"
```

---

### Task 3: Milvus Store Adapter

**Files:**
- Create: `app/infrastructure/milvus_store.py`
- Test: `tests/unit/test_milvus_store.py`
- Test: `tests/integration/test_milvus_store.py`

**Interfaces:**
- Produces: `MilvusChunkStore.ensure_collection()`, `upsert_document_chunks(chunks: Sequence[MilvusChunk])`, `search_dense(knowledge_base_id: UUID, query_vector: Sequence[float], limit: int) -> list[RetrievedChunk]`, `search_sparse(knowledge_base_id: UUID, query_text: str, limit: int) -> list[RetrievedChunk]`, `delete_document(document_id: UUID)`.
- Consumes: settings from Task 1 and ranking contracts from Task 2.

- [ ] **Step 1: Write failing unit contract tests with a fake Milvus client**

```python
def test_delete_document_uses_document_filter():
    fake = FakeMilvusClient()
    store = MilvusChunkStore(client=fake, collection_name="rag_chunks", embedding_dimension=3)

    store.delete_document(uuid.UUID("00000000-0000-0000-0000-000000000001"))

    assert fake.deleted_filter == 'document_id == "00000000-0000-0000-0000-000000000001"'
```

- [ ] **Step 2: Run unit test to verify failure**

Run: `uv run --no-sync pytest tests/unit/test_milvus_store.py -v`

Expected: FAIL because `MilvusChunkStore` does not exist.

- [ ] **Step 3: Implement adapter**

Implement collection creation with scalar fields, dense vector field, text/BM25 field, indexes, document-level insert replacement, dense search, sparse search, and document cleanup. Keep Milvus client details inside this adapter.

- [ ] **Step 4: Add real integration test**

Use Docker Milvus. The test inserts chunks into two knowledge bases, searches with one knowledge base filter, and asserts results do not include the other knowledge base.

Run: `uv run --no-sync pytest tests/integration/test_milvus_store.py -v`

Expected: PASS when Milvus service is running.

- [ ] **Step 5: Commit**

```powershell
git add app/infrastructure/milvus_store.py tests/unit/test_milvus_store.py tests/integration/test_milvus_store.py
git commit -m "feat: 增加 Milvus chunk 存储适配器"
```

---

### Task 4: Real Embedding and Reranker Clients

**Files:**
- Create: `app/infrastructure/model_clients.py`
- Test: `tests/unit/test_model_clients.py`
- Test: `tests/integration/test_external_model_clients.py`

**Interfaces:**
- Produces: `EmbeddingClient.embed_texts(texts: Sequence[str]) -> list[list[float]]`, `RerankerClient.rerank(query: str, chunks: Sequence[RankedChunk], limit: int) -> list[RankedChunk]`.
- Consumes: `httpx` or OpenAI-compatible SDK, settings from Task 1.

- [ ] **Step 1: Write failing HTTP contract tests**

```python
async def test_embedding_client_posts_openai_compatible_payload(respx_mock):
    route = respx_mock.post("https://api.example.test/v1/embeddings").mock(
        return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
    )
    client = EmbeddingClient(base_url="https://api.example.test/v1", api_key="key", model="m")

    vectors = await client.embed_texts(["hello"])

    assert vectors == [[0.1, 0.2]]
    assert route.calls.last.request.headers["authorization"] == "Bearer key"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run --no-sync pytest tests/unit/test_model_clients.py -v`

Expected: FAIL because clients do not exist.

- [ ] **Step 3: Implement clients**

Embedding client must call OpenAI-compatible `/embeddings`. Reranker client must call the configured rerank endpoint with query and documents, parse scores, and preserve chunk metadata.

- [ ] **Step 4: Add external tests guarded by marker**

External tests must skip unless `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` and required keys exist. When enabled, they call the real Embedding and Reranker APIs and assert non-empty vectors and reranked scores.

- [ ] **Step 5: Verify local tests**

Run: `uv run --no-sync pytest tests/unit/test_model_clients.py -v`

Expected: PASS without external credentials.

- [ ] **Step 6: Commit**

```powershell
git add app/infrastructure/model_clients.py tests/unit/test_model_clients.py tests/integration/test_external_model_clients.py pyproject.toml uv.lock
git commit -m "feat: 接入真实 Embedding 与 Reranker 客户端"
```

---

### Task 5: Hybrid Retrieval Service and API Query Path

**Files:**
- Create: `app/services/retrieval.py`
- Modify: `app/api/dependencies.py`
- Modify: `app/api/routes/rag.py`
- Test: `tests/unit/test_retrieval_service.py`
- Test: `tests/integration/test_rag_api.py`

**Interfaces:**
- Produces: `HybridRetrievalService.query(knowledge_base_id: UUID, query: str, limit: int) -> RetrievalAnswerContext`.
- Consumes: `MilvusChunkStore`, `EmbeddingClient`, `RerankerClient`, `fuse_rrf`.

- [ ] **Step 1: Write failing service test**

```python
async def test_hybrid_retrieval_filters_by_knowledge_base():
    store = FakeMilvusStore()
    service = HybridRetrievalService(
        store=store, embeddings=FakeEmbeddingClient(), reranker=FakeReranker()
    )
    kb_id = uuid.uuid4()

    await service.query(knowledge_base_id=kb_id, query="refund policy", limit=5)

    assert store.last_dense_filter_knowledge_base_id == kb_id
    assert store.last_sparse_filter_knowledge_base_id == kb_id
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run --no-sync pytest tests/unit/test_retrieval_service.py -v`

Expected: FAIL because `HybridRetrievalService` does not exist.

- [ ] **Step 3: Implement service**

The service embeds query text, runs dense and sparse Milvus search with the same knowledge base filter, fuses with RRF, dedupes, reranks, and returns evidence with stable citation labels.

- [ ] **Step 4: Wire API route**

`POST /api/v1/rag/query` must use the hybrid retrieval service. Response should include answer placeholder text assembled from evidence until Stage 5 adds LLM generation, plus source chunks with document IDs.

- [ ] **Step 5: Verify API tests**

Run:

```powershell
uv run --no-sync pytest tests/unit/test_retrieval_service.py -v
uv run --no-sync pytest tests/integration/test_rag_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/services/retrieval.py app/api/dependencies.py app/api/routes/rag.py tests/unit/test_retrieval_service.py tests/integration/test_rag_api.py
git commit -m "feat: 将 RAG 查询接入 Milvus 混合检索"
```

---

### Task 6: Worker Indexing, Retry, and Delete Cleanup

**Files:**
- Modify: `app/services/ingestion.py`
- Modify: `app/services/documents.py`
- Modify: `app/api/dependencies.py`
- Test: `tests/unit/test_ingestion_service.py`
- Test: `tests/integration/test_document_service.py`
- Test: `tests/e2e/test_async_ingestion.py`

**Interfaces:**
- Consumes: `MilvusChunkStore.upsert_document_chunks`, `MilvusChunkStore.delete_document`.
- Produces: ingestion completion writes Milvus chunks before task completion.

- [ ] **Step 1: Write failing cleanup test**

```python
async def test_retry_deletes_existing_milvus_chunks_before_enqueue():
    milvus = FakeMilvusStore()
    service = DocumentService(
        documents=FakeDocumentRepository(),
        tasks=FakeTaskRepository(),
        queue=FakeIngestionQueue(),
        storage=FakeObjectStorage(),
        milvus_store=milvus,
    )

    await service.retry(knowledge_base_id=kb_id, document_id=document_id)

    assert milvus.deleted_document_ids == [document_id]
```

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `uv run --no-sync pytest tests/unit/test_ingestion_service.py tests/integration/test_document_service.py -v`

Expected: FAIL because services do not call Milvus cleanup/write.

- [ ] **Step 3: Implement worker Milvus write**

Worker must delete old document chunks, insert the new chunk batch, and only then mark document/task completed. On Milvus failure, task status becomes failed with stage `indexing`.

- [ ] **Step 4: Implement retry/delete cleanup**

Retry deletes document chunks before creating the new task. Delete removes MinIO source/parsed objects and Milvus chunks before database deletion.

- [ ] **Step 5: Verify stage tests**

Run:

```powershell
uv run --no-sync pytest tests/unit/test_ingestion_service.py tests/integration/test_document_service.py -v
uv run --no-sync pytest tests/e2e/test_async_ingestion.py -v
```

Expected: PASS with Docker infrastructure.

- [ ] **Step 6: Commit**

```powershell
git add app/services/ingestion.py app/services/documents.py app/api/dependencies.py tests/unit/test_ingestion_service.py tests/integration/test_document_service.py tests/e2e/test_async_ingestion.py
git commit -m "feat: 摄取重试删除同步清理 Milvus 索引"
```

---

### Task 7: Stage 4 Documentation and Acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`
- Create: `docs/plans/2026-08-09-stage-4-progress.md`

**Interfaces:**
- Consumes: Tasks 1-6 verification results.
- Produces: user-facing Stage 4 deployment and verification instructions.

- [ ] **Step 1: Update README**

Document Milvus services, new env vars, query path, external API requirements, and Docker commands.

- [ ] **Step 2: Update roadmap**

Add Stage 4 completion row with actual verification commands and learning review questions.

- [ ] **Step 3: Run final Stage 4 gates**

Run:

```powershell
docker compose config --quiet
docker compose up -d postgres redis minio minio-init milvus-etcd milvus-minio milvus-standalone api worker
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
```

Expected: all non-external gates pass.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/learning-roadmap.md docs/plans/2026-08-09-stage-4-progress.md
git commit -m "docs: 完成阶段四混合检索验收记录"
```
