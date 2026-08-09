# 阶段 9：评估与求职交付实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可复现的 RAG 检索评估，并完成最终架构文档、源码导读、Yuxi 对照、评估报告、面试材料和 README，使项目能以真实完成能力用于复盘和求职。

**Architecture:** `app/evaluation` 提供数据集 schema、fixture ingestion、retrieval evaluator 和 metrics；命令行脚本生成 Markdown 报告；最终文档只描述已实现且验证过的功能。

**Tech Stack:** Python CLI, Pydantic, HybridRetrievalService, pytest, Markdown reports, Docker Compose verification.

## Global Constraints

- Evaluation compares Dense, BM25, RRF, and Rerank.
- Metrics include Recall@K, MRR, citation hit rate, and optional judge faithfulness score.
- Career-facing materials must describe only capabilities that are implemented and verified in this repository.
- README, `.env.example`, Docker Compose, roadmap, and final delivery documents stay synchronized with the implemented stage.
- Every `Fake*` type shown in test snippets is a test-local class defined in the same test file immediately above the test, implementing only the attributes and methods asserted by that test.

---

## File Structure

- Create `app/evaluation/__init__.py`
- Create `app/evaluation/dataset.py`
- Create `app/evaluation/metrics.py`
- Create `app/evaluation/runner.py`
- Create `app/evaluation/report.py`
- Create `scripts/run_evaluation.py`
- Create `tests/unit/test_evaluation_metrics.py`
- Create `tests/unit/test_evaluation_dataset.py`
- Create `tests/integration/test_evaluation_runner.py`
- Create `docs/architecture.md`
- Create `docs/source-code-guide.md`
- Create `docs/yuxi-comparison.md`
- Create `docs/rag-evaluation.md`
- Create `docs/interview-guide.md`
- Modify `README.md`
- Modify `docs/learning-roadmap.md`
- Create `docs/plans/2026-08-09-stage-9-progress.md`

---

### Task 1: Evaluation Dataset Schema

**Files:**
- Create: `app/evaluation/__init__.py`
- Create: `app/evaluation/dataset.py`
- Test: `tests/unit/test_evaluation_dataset.py`

**Interfaces:**
- Produces: `EvaluationDataset`, `EvaluationQuestion`, `ExpectedCitation`, `load_dataset(path: Path) -> EvaluationDataset`.
- Consumes: JSON or YAML local dataset file.

- [ ] **Step 1: Write failing dataset test**

```python
def test_load_dataset_validates_expected_documents(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "id": "q1",
                        "question": "What is the retention policy?",
                        "expected_document_ids": ["00000000-0000-0000-0000-000000000001"],
                        "expected_citations": [{"document_id": "00000000-0000-0000-0000-000000000001"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    dataset = load_dataset(path)

    assert dataset.questions[0].id == "q1"
    assert dataset.questions[0].expected_document_ids[0] == uuid.UUID("00000000-0000-0000-0000-000000000001")
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_evaluation_dataset.py -v`

Expected: FAIL because evaluation dataset module is missing.

- [ ] **Step 3: Implement dataset schema**

Use Pydantic models. Require question ID, question text, expected document IDs, and expected citations. Optional fields: expected answer facts and tags.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_evaluation_dataset.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/evaluation/__init__.py app/evaluation/dataset.py tests/unit/test_evaluation_dataset.py
git commit -m "feat: 定义 RAG 评估数据集结构"
```

---

### Task 2: Retrieval Metrics

**Files:**
- Create: `app/evaluation/metrics.py`
- Test: `tests/unit/test_evaluation_metrics.py`

**Interfaces:**
- Produces: `recall_at_k(expected: set[str], retrieved: Sequence[str], k: int) -> float`, `mrr(expected: set[str], retrieved: Sequence[str]) -> float`, `citation_hit_rate(expected: set[str], actual: set[str]) -> float`.
- Consumes: dataset expected IDs and retrieved IDs.

- [ ] **Step 1: Write failing metric tests**

```python
def test_recall_at_k_counts_expected_documents_in_top_k():
    assert recall_at_k({"a", "b"}, ["c", "a", "b"], k=2) == 0.5


def test_mrr_returns_inverse_first_relevant_rank():
    assert mrr({"b"}, ["a", "b", "c"]) == 0.5


def test_citation_hit_rate_requires_expected_citation_match():
    assert citation_hit_rate({"doc1#chunk1"}, {"doc1#chunk1", "doc2#chunk9"}) == 1.0
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --no-sync pytest tests/unit/test_evaluation_metrics.py -v`

Expected: FAIL because metrics module is missing.

- [ ] **Step 3: Implement metrics**

Return `0.0` when expected set is empty. Do not divide by zero. Keep functions pure.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_evaluation_metrics.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/evaluation/metrics.py tests/unit/test_evaluation_metrics.py
git commit -m "feat: 实现 RAG 评估指标"
```

---

### Task 3: Evaluation Runner

**Files:**
- Create: `app/evaluation/runner.py`
- Create: `scripts/run_evaluation.py`
- Test: `tests/integration/test_evaluation_runner.py`

**Interfaces:**
- Produces: `EvaluationRunner.run(dataset: EvaluationDataset) -> EvaluationResult`.
- Consumes: `HybridRetrievalService` and metrics from Task 2.

- [ ] **Step 1: Write failing runner test**

```python
async def test_runner_compares_retrieval_modes():
    runner = EvaluationRunner(retriever=FakeRetriever())
    dataset = EvaluationDataset(
        questions=[
            EvaluationQuestion(
                id="q1",
                question="retention",
                expected_document_ids=[uuid.UUID("00000000-0000-0000-0000-000000000001")],
                expected_citations=[],
            )
        ]
    )

    result = await runner.run(dataset)

    assert {"dense", "bm25", "rrf", "rerank"} <= set(result.mode_results)
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/integration/test_evaluation_runner.py -v`

Expected: FAIL because runner does not exist.

- [ ] **Step 3: Implement runner**

Runner calls retriever modes separately: dense only, BM25 only, RRF, and Rerank. It computes metrics per mode and aggregate averages.

- [ ] **Step 4: Implement CLI**

`scripts/run_evaluation.py` accepts dataset path and output report path. It must fail clearly when services or credentials are missing.

- [ ] **Step 5: Verify runner**

Run: `uv run --no-sync pytest tests/integration/test_evaluation_runner.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/evaluation/runner.py scripts/run_evaluation.py tests/integration/test_evaluation_runner.py
git commit -m "feat: 增加检索评估 Runner"
```

---

### Task 4: Markdown Report Generation

**Files:**
- Create: `app/evaluation/report.py`
- Test: `tests/unit/test_evaluation_report.py`

**Interfaces:**
- Produces: `render_markdown_report(result: EvaluationResult) -> str`.
- Consumes: evaluation result from Task 3.

- [ ] **Step 1: Write failing report test**

```python
def test_report_includes_mode_table():
    report = render_markdown_report(fake_evaluation_result())

    assert "| Mode | Recall@K | MRR | Citation Hit Rate |" in report
    assert "Dense" in report
    assert "Rerank" in report
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_evaluation_report.py -v`

Expected: FAIL because report renderer is missing.

- [ ] **Step 3: Implement renderer**

Render summary, dataset size, per-mode metrics table, per-question failures, and interpretation notes.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_evaluation_report.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/evaluation/report.py tests/unit/test_evaluation_report.py
git commit -m "feat: 生成 RAG 评估 Markdown 报告"
```

---

### Task 5: Final Technical Documentation

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/source-code-guide.md`
- Create: `docs/yuxi-comparison.md`
- Create: `docs/rag-evaluation.md`
- Modify: `README.md`
- Test: manual review plus `ruff format --check .`

**Interfaces:**
- Consumes: implemented stages 0-9.
- Produces: final project documentation.

- [ ] **Step 1: Write architecture document**

Cover module boundaries, storage responsibilities, ingestion flow, retrieval flow, Agent flow, SSE flow, failure recovery, and deployment topology.

- [ ] **Step 2: Write source code guide**

Guide readers through the execution chain by files and symbols: config, API, services, repositories, parsers, retriever, agent, observability, evaluation.

- [ ] **Step 3: Write Yuxi comparison**

Compare the learning implementation with the original Yuxi concepts at the architecture level. Include what was kept, simplified, and intentionally omitted.

- [ ] **Step 4: Write evaluation report**

Run the evaluation command on the committed dataset and save the generated report to `docs/rag-evaluation.md`.

- [ ] **Step 5: Update README final version**

README must document all services, env vars, deployment commands, API surface, quality gates, external verification, and known limitations.

- [ ] **Step 6: Commit**

```powershell
git add docs/architecture.md docs/source-code-guide.md docs/yuxi-comparison.md docs/rag-evaluation.md README.md
git commit -m "docs: 完成最终架构源码导读与评估文档"
```

---

### Task 6: Interview Guide and Resume Material

**Files:**
- Create: `docs/interview-guide.md`
- Modify: `docs/learning-roadmap.md`
- Create: `docs/plans/2026-08-09-stage-9-progress.md`

**Interfaces:**
- Consumes: verified final project capabilities.
- Produces: truthful career-facing material.

- [ ] **Step 1: Write one-minute and five-minute project introductions**

Each introduction must mention concrete implemented components and avoid unverifiable claims.

- [ ] **Step 2: Write resume bullets**

Bullets must reference actual technologies and validated outcomes: async ingestion, Milvus hybrid retrieval, LangGraph agent, SSE citations, parser services, observability, and evaluation.

- [ ] **Step 3: Write interview Q&A**

Include questions on consistency, failure recovery, RRF, knowledge base isolation, parser selection, Agent loop limit, SSE transaction boundaries, observability, and evaluation limits.

- [ ] **Step 4: Update learning roadmap**

Add Stage 9 completion row and final mastery/remaining-review notes.

- [ ] **Step 5: Commit**

```powershell
git add docs/interview-guide.md docs/learning-roadmap.md docs/plans/2026-08-09-stage-9-progress.md
git commit -m "docs: 完成求职交付与阶段九复盘"
```

---

### Task 7: Final End-to-End Acceptance

**Files:**
- Modify: `README.md` if final verification reveals command mismatch.
- Test: Docker and external verification commands.

**Interfaces:**
- Consumes: all prior stages.
- Produces: final verified project state.

- [ ] **Step 1: Run local production gates**

Run:

```powershell
docker compose config --quiet
docker compose up -d
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync alembic current --check-heads
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
```

Expected: PASS.

- [ ] **Step 2: Run external verification when credentials are configured**

Run:

```powershell
docker compose exec api uv run --no-sync pytest -m external -v
```

Expected: PASS if Chat, Embedding, Reranker, Langfuse, MinerU, and PaddleX are configured and reachable. If credentials are missing, record skipped tests and the exact missing variables.

- [ ] **Step 3: Run evaluation**

Run:

```powershell
docker compose exec api uv run --no-sync python scripts/run_evaluation.py --dataset docs/evaluation/sample-dataset.json --output docs/rag-evaluation.md
```

Expected: report regenerated successfully.

- [ ] **Step 4: Final commit**

```powershell
git add README.md docs/rag-evaluation.md docs/plans/2026-08-09-stage-9-progress.md
git commit -m "chore: 完成 RAG Agent 最终验收"
```
