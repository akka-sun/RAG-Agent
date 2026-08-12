# 阶段 9 进度记录：评估与交付收尾

日期：2026-08-09

## 完成范围

- 新增 `app/evaluation`：
  - `dataset.py`：JSON/YAML 评估数据集 schema。
  - `metrics.py`：Recall@K、MRR、citation hit rate。
  - `runner.py`：Dense、BM25、RRF、Rerank 四模式评估。
  - `report.py`：Markdown 报告生成。
- 新增 `scripts/run_evaluation.py`，用于 Docker 环境内生成评估报告。
- 新增最终交付文档：
  - `docs/architecture.md`
  - `docs/source-code-guide.md`
  - `docs/yuxi-comparison.md`
  - `docs/rag-evaluation.md`
  - `docs/interview-guide.md`
- README 与学习路线已同步到阶段 9。

## 验收结果

- 评估 schema、metrics、report 单元测试通过。
- 评估 Runner 集成测试通过。
- 最终全量门禁：
  - `docker compose config --quiet`：通过。
  - Alembic 主库/测试库升级到 head：通过。
  - `ruff format --check .`：通过。
  - `ruff check .`：通过。
  - `pyright`：通过。
  - `pytest tests/unit -v`：160 passed。
  - `pytest tests/integration -v`：47 passed、6 skipped。
  - `pytest tests/e2e -v`：1 passed。
  - `pytest -m external -v`：6 skipped、208 deselected。

## 后续生产验收建议

1. 配置真实 Chat、Embedding、Reranker API。
2. 启动 `docker compose --profile parser up -d mineru paddlex`。
3. 配置 Langfuse 项目地址与 key。
4. 使用真实 PDF 和问答集运行 `pytest -m external -v` 与 `scripts/run_evaluation.py`。
