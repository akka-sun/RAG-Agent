# Yuxi 对照复盘

本项目对标的是“业务级 Agentic RAG 后端”，而不是只调用一次 LLM 的薄封装。与常见教程项目相比，RAG Agent 的差异在于：

| 维度 | 常见 Demo | RAG Agent 当前实现 |
| --- | --- | --- |
| 文档摄取 | 同步解析并写内存 | ARQ 异步任务、状态机、重试、失败补偿 |
| 存储 | 单进程内存或本地文件 | PostgreSQL、MinIO、Redis、Milvus |
| 检索 | 单向量召回 | Dense + BM25 + RRF + Reranker |
| PDF | 直接读文本或未支持 | MinerU/PaddleX Docker 解析，统一 `ParsedDocument` |
| Agent | Prompt + 一次检索 | LangGraph 分类、改写、检索循环、证据判断、生成 |
| 会话 | 不落库或只存文本 | conversation/message/citation 快照持久化 |
| 可观测性 | 打印日志 | trace context、结构化日志、可选 Langfuse |
| 评估 | 主观试问 | Recall@K、MRR、citation hit rate 报告 |

## 简历表达边界

可以写：实现了生产化 Agentic RAG 后端，支持异步摄取、PDF parser、Milvus 混合检索、LangGraph Agent、SSE 会话、结构化可观测性和可复现检索评估。

不应写：已完成权限系统、多租户计费、线上灰度、自动 judge 忠实度、Kubernetes 生产部署。这些不是当前仓库已验证能力。

