# 阶段 4 验收记录：Milvus 混合检索

日期：2026-08-09

## 完成范围

- Docker Compose 增加真实 Milvus standalone 拓扑：`milvus-etcd`、`milvus-minio`、`milvus-standalone`。
- 配置新增 Milvus、OpenAI-compatible Embedding API、Reranker API 环境变量。
- 新增 PyMilvus 适配层：
  - Collection schema 保存知识库 ID、文档 ID、文件名、chunk 文本、字符范围、dense vector 和 BM25 sparse vector。
  - Milvus BM25 Function 自动从文本字段生成 sparse vector。
  - dense search 与 sparse search 均强制使用 `knowledge_base_id` 过滤。
  - 文档级 upsert/delete 使用 `knowledge_base_id + document_id` 清理并 flush。
- 新增混合检索核心：
  - `RetrievedChunk` / `RankedChunk`
  - RRF 融合
  - chunk 去重
  - 远程 Reranker 后排序
- 新增真实 HTTP 客户端：
  - `EmbeddingClient` 请求 OpenAI-compatible `/embeddings`
  - `RerankerClient` 请求 `{base}/rerank`
- worker 摄取链路改为写入 Milvus。
- `/rag/query` 改为使用 Milvus 混合检索服务并返回稳定引用。
- retry/delete 文档时同步清理 Milvus 索引。

## 验证记录

已执行并通过：

```powershell
docker compose config --quiet
docker compose up -d milvus-etcd milvus-minio milvus-standalone
docker compose exec api uv run --no-sync pytest tests/unit/test_config.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_hybrid_retrieval.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_milvus_store.py -v
docker compose exec api uv run --no-sync pytest tests/integration/test_milvus_store.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_model_clients.py -v
docker compose exec api uv run --no-sync pytest tests/integration/test_external_model_clients.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_retrieval_service.py tests/integration/test_rag_api.py -v
docker compose exec api uv run --no-sync pytest tests/unit/test_ingestion_service.py tests/unit/test_worker_settings.py tests/unit/test_milvus_store.py tests/integration/test_document_service.py tests/e2e/test_async_ingestion.py -v
```

结果摘要：

- 配置与 Compose 校验通过。
- Milvus 真实集成测试证明知识库过滤不会串库。
- 外部模型测试默认 skip；需要真实凭据和 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 才会调用实际 API。
- 端到端测试证明上传、worker 摄取、Milvus 检索、重复执行幂等、删除清理均通过。

## 关键设计决定

1. Redis 只保留 ARQ 队列职责，不再作为生产检索索引。
2. Milvus Store 使用同步 PyMilvus 客户端，并在 async 上层通过线程桥接。
3. RRF 只融合名次，不混加 dense 与 BM25 原始分数。
4. delete/upsert 后调用 Milvus flush，避免验收时读到旧索引状态。
5. 本地开发未配置模型 key 时 worker 使用 Hashing Embedding fallback；生产模式或配置 key 时使用真实 Embedding API。

## 下一阶段入口

阶段 5 将在 `HybridRetrievalService` 基础上接入 LangGraph Agent：

- Agent 自主判断是否检索。
- 最多三轮检索/查询改写。
- 使用真实 OpenAI-compatible Chat API 生成带引用回答。
- 使用 PostgreSQL Checkpointer 保存 Agent 状态。
