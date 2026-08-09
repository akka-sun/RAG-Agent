# 面试材料

## 一分钟介绍

我做了一个生产化 Agentic RAG 后端：FastAPI 提供 API，ARQ Worker 异步摄取文档，PostgreSQL 保存业务状态和 LangGraph checkpoint，MinIO 保存原文与解析结果，Milvus 做 Dense + BM25 混合检索，Agent 通过 LangGraph 完成查询改写、检索循环和带引用回答。项目还接入了 MinerU/PaddleX PDF 解析、SSE 会话流、结构化日志、可选 Langfuse Trace，以及可复现的检索评估报告。

## 五分钟展开

1. 摄取链路：上传后立即返回 202，后台 Worker 通过数据库 claim 保证幂等，解析、分块、向量化、索引分阶段更新进度。
2. 检索链路：Milvus 同时保存 dense vector 与 BM25 字段；查询时双路召回，RRF 融合，再用 Reranker 排序。
3. Agent 链路：LangGraph 先判断是否需要检索，需要时改写查询并最多检索三次，防止无限工具调用。
4. 会话链路：SSE 输出 token/citation/end 事件，最终消息和引用快照同事务落库，刷新后可复现。
5. 可观测与评估：trace ID 贯穿请求和任务，Langfuse 可选导出；评估 Runner 对比 Dense、BM25、RRF、Rerank。

## 高频追问

**为什么不用同步摄取？** PDF 解析、Embedding 和索引可能耗时且失败点多；异步任务能返回明确状态、支持重试和补偿。

**为什么 RRF 而不是直接加分？** Dense 与 BM25 分数尺度不同，直接加分会偏向某一路；RRF 基于排名融合，更适合异构召回。

**为什么 citation 要落库？** 索引和解析结果后续可能重建；快照能保证历史回答仍能解释来源。

**为什么外部测试默认 skip？** 默认 CI 应稳定且不消耗额度；真实模型、Parser、Langfuse 连通性通过显式开关单独验收。

**最大的生产风险是什么？** 真实 PDF/OCR 质量、Embedding 维度迁移、外部 API 限流与超时、Milvus schema 演进和权限/租户隔离。

