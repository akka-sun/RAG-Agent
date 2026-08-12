# 真实模型评测数据集

项目提供 `scripts/run_benchmarks.py`，使用公开数据集和真实 OpenAI-compatible API，分别评测文本检索、Agentic RAG 和图片/PDF 处理。

## 三个数据集

| 目标 | 数据集 | 规模 | 主要指标 |
| --- | --- | ---: | --- |
| 文本检索 | [NanoSciFact](https://huggingface.co/datasets/zeta-alpha-ai/NanoSciFact) | 2,919 篇语料、50 个查询、56 条 qrels | Recall@K、MRR、Dense/BM25/RRF/Rerank 对比 |
| Agentic RAG | [HotpotQA Distractor](https://huggingface.co/datasets/hotpotqa/hotpot_qa) validation | 7,405 条多跳问答 | Answer EM/F1、支持文档召回、检索轮数、Chat 调用数 |
| 图片/PDF | [ChartQA](https://huggingface.co/datasets/HuggingFaceM4/ChartQA) test | 2,500 张图表问答 | 答案准确率、解析成功率、解析/生成延迟 |

NanoSciFact 的语料和 qrels 通过 Hugging Face rows API 下载到隔离的内存索引，Embedding 和 Reranker 仍调用项目配置的真实服务。HotpotQA 每道题的 10 篇 distractor context 作为临时知识库，Agent 直接复用项目的 LangGraph 查询改写、检索循环和回答节点。ChartQA 图片先生成单页 PDF，再调用项目的 MinerU 或 PaddleX，解析后的 Markdown/文本交给真实 Chat 模型回答。

## 配置

检索和 Agentic RAG 需要：

```dotenv
RAG_AGENT_EMBEDDING_BASE_URL=https://api.openai.com/v1
RAG_AGENT_EMBEDDING_API_KEY=
RAG_AGENT_EMBEDDING_MODEL=text-embedding-3-small
RAG_AGENT_EMBEDDING_DIMENSION=1536
RAG_AGENT_RERANK_BASE_URL=
RAG_AGENT_RERANK_API_KEY=
RAG_AGENT_RERANK_MODEL=
```

Agentic RAG 和 ChartQA 需要：

```dotenv
RAG_AGENT_CHAT_BASE_URL=https://api.openai.com/v1
RAG_AGENT_CHAT_API_KEY=
RAG_AGENT_CHAT_MODEL=gpt-4.1-mini
```

图片/PDF 还需要启动一个解析器，并把地址配置为 API/Worker 容器可访问的地址：

```dotenv
RAG_AGENT_DEFAULT_PDF_PARSER=mineru
RAG_AGENT_MINERU_BASE_URL=http://mineru:8000
RAG_AGENT_PADDLEX_BASE_URL=http://paddlex:8080
```

Reranker 服务必须提供 OpenAI-compatible `/rerank` 接口，返回 `results` 或 `data`，每项至少包含 `index` 和 `relevance_score`。

## 运行

首次建议先跑小子集：

```powershell
docker compose exec api uv run --no-sync python -m scripts.run_benchmarks `
  --mode all `
  --retrieval-queries 10 `
  --retrieval-corpus 500 `
  --agentic-questions 5 `
  --image-questions 5 `
  --output reports/real-benchmarks.json
```

完整 NanoSciFact 语料和 50 个查询：

```powershell
docker compose exec api uv run --no-sync python -m scripts.run_benchmarks `
  --mode retrieval `
  --output reports/nanoscifact-retrieval.json
```

`--mode agentic` 和 `--mode chartqa` 可以单独运行。脚本在下载数据集或调用模型前检查必需环境变量；缺少配置时会列出变量名并退出，不会退回 HashingEmbedder 或 Fake 模型。

## 解释结果

- NanoSciFact 的 `citation_hit_rate` 没有 qrels citation 粒度，因此该项为 0，重点看 Recall@K 和 MRR。
- HotpotQA 的支持文档召回按 supporting-facts 的文章标题计算；答案 EM/F1 只比较最终回答，不使用 LLM judge。
- ChartQA 评测的是“图片 -> PDF -> MinerU/PaddleX -> Chat”链路，不是直接把原图发送给视觉模型。若要测端到端视觉模型，应另接支持图片 content parts 的 Chat 客户端。
