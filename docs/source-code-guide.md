# 源码导读

## 入口层

- `app/main.py`：创建 FastAPI 应用、注册路由、初始化 LangGraph checkpoint、注入 HTTP trace。
- `app/api/routes/`：知识库、文档、摄取任务、RAG 查询、会话和 SSE API。
- `app/api/dependencies.py`：组装数据库、对象存储、Milvus、模型客户端、Service 和 Agent。

## 业务层

- `app/services/documents.py`：上传、重试、删除和跨存储补偿。
- `app/services/ingestion.py`：Worker 摄取主流程，负责解析、分块、向量化和索引。
- `app/services/retrieval.py`：Dense/BM25/RRF/Rerank 混合检索。
- `app/services/agent_chat.py`：调用 LangGraph Agent。
- `app/services/sse_chat.py`：会话流式输出与消息/引用落库。

## 基础设施层

- `app/infrastructure/milvus_store.py`：Milvus collection、schema、dense/BM25 search、delete/flush。
- `app/infrastructure/model_clients.py`：Embedding 与 Reranker 的 OpenAI-compatible HTTP 客户端。
- `app/infrastructure/chat_client.py`：Chat Completion 客户端。
- `app/infrastructure/object_storage.py`：MinIO 原文和解析结果存储。
- `app/infrastructure/queue.py`：ARQ 队列投递。

## Parser 与评估

- `app/parsers/`：本地 Markdown/TXT、MinerU、PaddleX 和统一 parser router。
- `app/evaluation/`：评估数据集、指标、Runner 和 Markdown 报告。
- `scripts/run_evaluation.py`：命令行评估入口。

## 测试分层

- `tests/unit/`：不依赖真实外部服务，覆盖纯逻辑、错误处理和服务边界。
- `tests/integration/`：使用 Docker 中的 PostgreSQL、Milvus、MinIO、Redis 等真实基础设施。
- `tests/e2e/`：覆盖 API + Worker + 存储 + 索引的完整链路。
- `external` marker：真实模型、Parser、Langfuse 连通性测试，默认跳过。

