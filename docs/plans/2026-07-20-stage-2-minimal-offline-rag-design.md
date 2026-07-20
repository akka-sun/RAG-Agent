# 阶段 2：最小离线 RAG 设计

日期：2026-07-20

## 1. 目标

在不接入外部模型、对象存储、队列或向量数据库的前提下，建立一条可通过 HTTP 验证的最小 RAG 链路：将 Markdown/TXT 文本同步分块、生成确定性向量、写入按知识库隔离的进程内索引，再根据查询召回 Top-K chunks 并组装带稳定引用的本地回答。

阶段结束时，学习者应能解释摄取链路和查询链路、chunk size 与 overlap 的影响、余弦相似度的含义，以及“没有召回证据”和“回答没有正确使用证据”的区别。

## 2. 范围

### 2.1 本阶段实现

- `POST /api/v1/rag/documents`：使用 JSON 提交已存在的知识库 ID、`.md`/`.txt` 文件名和文本内容，同步完成分块与索引。
- `POST /api/v1/rag/query`：提交知识库 ID、查询文本和 Top-K，返回确定性本地回答与结构化引用。
- 固定字符窗口分块，默认 `chunk_size=500`、`overlap=100`，保留可验证的字符区间。
- 兼容英文单词、数字和单个中日韩统一表意字符的确定性 Hashing Embedding，固定维度为 64，并进行 L2 归一化。
- 使用归一化向量点积计算余弦相似度，只返回分数大于 0 的候选。
- 按 `knowledge_base_id` 隔离进程内索引。
- 回答使用 `[S1]`、`[S2]` 等稳定标签；没有证据时返回固定文本且引用为空。
- 摄取与查询前通过现有 `KnowledgeBaseService.get()` 校验知识库存在，不允许幽灵知识库。
- 单元测试覆盖分块边界、overlap、Embedding 确定性、相似度排序、知识库隔离、无召回和回答引用。
- 集成测试覆盖知识库创建、文本摄取、查询、引用和不存在知识库的统一 404。

### 2.2 本阶段不实现

- 真实 LLM、Embedding API 或 Reranker。
- multipart 文件上传、原始文件保存、Document PostgreSQL 模型。
- Redis、ARQ、MinIO、Milvus 或异步任务状态。
- Markdown AST、PDF 解析、语义分块、BM25、RRF 或混合检索。
- 索引持久化、服务重启恢复、文档更新和删除。
- 将进程内索引伪装成生产级存储。

## 3. 方案选择

采用“独立 RAG 核心模块 + 应用 Service + 薄 API”结构：

```text
HTTP JSON
  ↓
RAG Route
  ↓
RAGService
  ├─ KnowledgeBaseService：校验知识库
  ├─ chunk_text：切分字符窗口
  ├─ HashingEmbedder：生成确定性向量
  └─ InMemoryVectorStore：隔离索引与 Top-K 检索
  ↓
RAG Response：answer + sources
```

不把分块、向量计算或索引逻辑写进 Route；也不为未来 Milvus 或外部模型预设插件注册系统。核心类只提供阶段 2 实际需要的接口，后续阶段通过替换明确边界演进。

## 4. 核心数据结构

`app/rag/types.py` 定义：

- `TextChunk`：`text`、`start`、`end` 和序号。
- `IndexedChunk`：知识库 ID、文档 ID、文件名、chunk ID、文本、字符区间和向量。
- `SearchResult`：命中的 `IndexedChunk` 与余弦分数。

API Schema 定义：

- `RAGDocumentCreate`：`knowledge_base_id`、`filename`、`content`。
- `RAGDocumentResponse`：`document_id`、`chunk_count`。
- `RAGQueryRequest`：`knowledge_base_id`、`query`、`top_k`，其中 `top_k` 范围为 1～10，默认 3。
- `RAGSourceResponse`：`label`、文档与 chunk 标识、文件名、文本、字符区间和分数。
- `RAGQueryResponse`：`answer` 与 `sources`。

## 5. 分块规则

输入先统一换行为 `\n` 并去除首尾空白。空白文本由 Schema 拒绝。分块使用字符滑动窗口：

```text
第 1 块：[0, 500)
第 2 块：[400, 900)
第 3 块：[800, ...)
```

步长为 `chunk_size - overlap`。约束为 `chunk_size > 0` 且 `0 <= overlap < chunk_size`，非法配置立即抛出 `ValueError`。最后一块到达文本末尾后停止，不生成空 chunk。

固定字符窗口并非最终语义分块方案；选择它是因为行为完全确定，便于观察 chunk size、overlap 和召回之间的关系。阶段 3 再引入结构化递归分块。

## 6. 确定性 Embedding 与检索

Tokenizer 将文本转为小写英文/数字词元与单个 CJK 字符。每个词元通过 SHA-256 映射到 64 维向量的一个位置和正负符号，累加后进行 L2 归一化。相同文本在任意进程中得到相同向量，不使用 Python 的随机哈希。

索引按知识库 ID 保存 `IndexedChunk` 列表。查询时只遍历目标知识库，使用归一化向量点积作为余弦分数，过滤 `score <= 0`，按 `score` 降序、`chunk_id` 升序稳定排序并截取 Top-K。

该实现只用于学习数据流和确定性测试，不宣称具备语义 Embedding 的召回质量。

## 7. 回答与引用

存在检索结果时，Service 按排序生成：

```text
根据检索到的资料：
[S1] 第一段证据
[S2] 第二段证据
```

每个 `source` 使用与回答一致的标签，并包含原文、分数和字符区间。没有分数大于 0 的结果时返回 `未找到相关证据。`，`sources=[]`。本阶段不调用 LLM，因此“生成质量”只验证证据是否被稳定、可追溯地组织，而不评估自然语言能力。

## 8. 生命周期与一致性边界

进程内 Store 由 FastAPI 依赖提供为应用进程内单例；测试通过依赖覆盖使用全新 Store。服务重启后索引丢失，这是本阶段明确限制。

摄取和查询均先校验 PostgreSQL 中的知识库。知识库删除后，旧内存 chunks 暂不主动清理，但查询会因知识库不存在返回 404，因此脏索引不可被 API 检索。真正的文档删除、补偿和持久化清理在阶段 3 设计。

## 9. 错误处理

- 不存在的知识库：沿用 `KnowledgeBaseNotFoundError`，返回统一 404。
- 非 `.md`/`.txt` 文件名、空内容、空查询或非法 Top-K：由 Pydantic 校验返回统一 422。
- 非法分块配置属于编程错误，直接抛出 `ValueError`，不增加运行时回退。
- 未召回证据是正常业务结果，返回 200 和空引用，不作为异常。

## 10. 测试与验收

- 单元测试不访问 PostgreSQL 或网络。
- API 集成测试使用真实 `rag_agent_test` PostgreSQL，并为每个测试注入新的进程内 Store。
- Docker 内必须通过 Ruff format、Ruff check、Pyright、全部单元和集成测试。
- 真实 HTTP 验收必须先创建知识库，再摄取文本并查询，确认回答包含 `[S1]` 且 source 可追溯到同一文档。
- 学习进度只记录真实通过的测试证据和口述验收结果。

## 11. 验收标准

- [ ] Markdown/TXT JSON 文本可以同步分块并写入指定知识库的进程内索引。
- [ ] 相同文本生成相同向量，检索排序在测试中确定。
- [ ] 不同知识库之间不能互相召回 chunks。
- [ ] 查询返回本地回答和结构化 `[S1]` 引用；无证据返回固定空结果。
- [ ] 不存在知识库返回统一 404，非法输入返回统一 422。
- [ ] 所有验证在 Docker Compose 容器中通过，默认不依赖任何外部模型服务。
- [ ] 学习者能解释摄取/查询数据流、分块取舍、余弦相似度和召回与生成的区别。
