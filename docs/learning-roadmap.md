# RAG-Agent 从 0 到 100 学习路线

## 1. 学习目标

这不是一份照抄教程的任务清单。最终目标是同时具备以下能力：

- 独立实现 Agentic RAG 后端的核心链路。
- 能从 HTTP 请求一路解释到数据库、队列、解析、向量检索、Agent 和流式响应。
- 能为功能编写单元、集成和端到端测试。
- 能说明每个技术选择解决了什么问题、付出了什么代价。
- 能基于真实代码回答求职面试中的深入追问。

计划周期约 10 周，每周投入 10～20 小时。进度以掌握程度为准，不为了日期跳过验收。

## 2. 固定学习循环

每个任务遵循同一流程：

1. **理解问题**：先说明业务目标、基础概念和对应执行链路。
2. **阅读参照**：只阅读 Yuxi 中与当前任务直接相关的文件和符号。
3. **明确验收**：在编码前写清功能、测试和讲解标准。
4. **独立实现**：学习者先完成代码和测试。
5. **代码审查**：检查正确性、边界、结构、可读性和测试质量。
6. **修改验证**：在 Docker 环境运行格式化、检查和测试。
7. **口述验收**：解释数据流、设计理由、替代方案和失败路径。
8. **复盘记录**：更新已掌握内容和待复习问题。

帮助等级：

1. 概念提示和相关文件位置。
2. 函数签名、数据结构和伪代码。
3. 当前难点的小段参考代码。
4. 与学习者实现不同的完整对照示例。
5. 连续受阻或明确要求时，由指导者直接修改并逐段解释。

## 3. 阶段路线

### 阶段 0：Python 后端工程基础（0 → 10）

预计时间：第 1 周。

学习内容：

- Python 3.12 项目结构、虚拟环境与依赖管理。
- 类型标注、数据类、异常和上下文管理器。
- 同步、异步、协程和 I/O 密集任务。
- Pydantic Settings 与环境变量。
- Dockerfile、Docker Compose、容器网络和健康检查。
- pytest 基础、fixture 和 Arrange-Act-Assert。

成果：

- 创建独立 `RAG-Agent` Python 项目。
- 实现带配置加载和健康检查的最小 FastAPI 服务。
- 在 Docker 中启动并通过首个测试。

验收：

- 能解释 `async def` 不等于自动并行。
- 能解释宿主机端口、容器端口和服务名解析。
- 能独立添加一个配置项和对应测试。

### 阶段 1：FastAPI 与 PostgreSQL（10 → 20）

预计时间：第 2 周。

学习内容：

- HTTP 方法、状态码、请求校验和依赖注入。
- SQL、事务、索引、外键和连接池。
- SQLAlchemy 2.x 异步 ORM。
- Repository 与 Service 的职责边界。
- Alembic 迁移。

成果：

- 实现知识库创建、列表、详情和删除。
- 建立统一错误响应。
- 完成单元与数据库集成测试。

验收：

- 能从路由讲到事务提交。
- 能解释为什么路由不直接写 ORM 查询。
- 能从空数据库完成迁移并运行测试。

### 阶段 2：最小离线 RAG（20 → 35）

预计时间：第 3 周。

学习内容：

- RAG 的摄取与查询两条链路。
- 文本分块、overlap、Embedding 和余弦相似度。
- Prompt 中上下文与引用的组织方式。
- 召回率与生成质量的区别。

成果：

- 使用少量 Markdown/TXT 完成进程内最小 RAG。
- 暂时使用简单向量实现验证数据流。
- 为分块和检索编写确定性测试。

验收：

- 能手画完整 RAG 数据流。
- 能解释 chunk 太大或太小的影响。
- 能区分“没召回”与“模型没有正确使用证据”。

### 阶段 3：异步文档摄取（35 → 50）

预计时间：第 4～5 周。

学习内容：

- MinIO 对象存储。
- Redis 与 ARQ 队列。
- 任务状态机、幂等与失败重试。
- 跨 PostgreSQL、MinIO 和向量库的一致性与补偿。

成果：

- 文档上传后返回 `202`。
- Worker 完成解析、分块、Embedding 和索引。
- 支持任务轮询、失败原因、重试和删除。

验收：

- 能解释为什么不能把跨存储操作称为一个数据库事务。
- 能逐项说明每个失败点留下的状态及恢复方法。
- 重复执行任务不会产生可检索的重复 chunks。

### 阶段 4：Milvus 混合检索（50 → 65）

预计时间：第 5～6 周。

学习内容：

- Milvus Collection、Schema、索引和过滤表达式。
- 稠密向量检索与 BM25 的互补关系。
- Sparse Vector、RRF、候选去重和 Reranker。
- 批量写入与查询参数。

成果：

- 多知识库隔离的 Milvus 索引。
- Dense + BM25 双路召回。
- RRF 融合、去重和远程 Reranker。

验收：

- 能手算一个小型 RRF 示例。
- 能解释为什么不能直接相加 Dense 与 BM25 原始分数。
- 能通过测试证明知识库过滤不会串库。

### 阶段 5：LangGraph Agent（65 → 78）

预计时间：第 7 周。

学习内容：

- Agent State、Node、Edge、Tool Calling 和 Checkpointer。
- 普通 RAG 与 Agentic RAG 的差异。
- 工具循环上限、查询改写和证据不足处理。

成果：

- Agent 自主决定是否调用检索工具。
- 支持最多三次检索和查询改写。
- 使用 PostgreSQL Checkpointer 恢复图状态。

验收：

- 能解释每个节点读取和写入的状态。
- 能说明哪些问题不应检索。
- 能证明工具循环不会无限执行。

### 阶段 6：会话、SSE 与引用（78 → 86）

预计时间：第 8 周。

学习内容：

- SSE 协议、流式生成和断开连接。
- 业务消息与 LangGraph 内部消息的区别。
- 引用标识、来源快照和事务写入。

成果：

- 会话与消息持久化。
- SSE 输出 Agent 状态、检索事件、token 和引用。
- 引用精确到文档、页码或段落及 chunk。

验收：

- 能解释一个流式请求从进入 API 到结束的完整路径。
- 非法引用不能落库。
- 刷新后能够恢复会话和引用。

### 阶段 7：完整 PDF 解析（86 → 92）

预计时间：第 8～9 周。

学习内容：

- 统一解析器接口。
- MinerU 与 PaddleX 服务调用。
- PDF 页码、标题、段落和 OCR 结果归一化。
- GPU 容器与外部解析测试。

成果：

- PDF 上传时明确选择 MinerU 或 PaddleX。
- 生成统一 `ParsedDocument`。
- MinIO 保存结构化解析产物。

验收：

- 任一解析器失败时返回真实错误，不静默切换。
- 普通 PDF 与扫描件的引用元数据可追溯。
- 能解释解析器适配层为何存在。

### 阶段 8：工程质量与可观测性（92 → 97）

预计时间：第 9 周。

学习内容：

- 单元、集成和 E2E 测试边界。
- 确定性外部服务替身。
- 结构化日志、Trace 与 Langfuse。
- Ruff、Pyright 和迁移检查。

成果：

- 默认测试不依赖付费或不稳定外部服务。
- 真实外部服务测试使用独立标记。
- 关键摄取、检索和 Agent 链路可追踪。

验收：

- 能解释每类测试发现什么问题。
- 能通过日志和 Trace 定位一次失败发生在哪一阶段。
- Docker 内检查、测试和 E2E 全部通过。

### 阶段 9：评估与求职交付（97 → 100）

预计时间：第 10 周。

学习内容：

- Recall@K、MRR、引用命中率和回答忠实度。
- 消融实验与参数调整。
- 架构表达和面试追问。

成果：

- 比较 Dense、BM25、RRF 和 Rerank 的评估报告。
- 完成架构文档、源码导读和 Yuxi 对照文档。
- 完成真实可信的简历描述与面试材料。

验收：

- 能用一分钟和五分钟分别介绍项目。
- 能基于实验结果说明混合检索的价值与局限。
- 能独立回答核心实现、性能、一致性、失败恢复和测试问题。

## 4. 进度记录

每完成一个任务，在下表追加记录：

| 日期 | 阶段 | 完成内容 | 测试证据 | 已掌握 | 待复习 |
|---|---|---|---|---|---|
| 2026-07-17 | 需求设计 | 确认最终架构和教学方式 | 设计评审通过 | 项目边界 | 待开始阶段 0 |
| 2026-07-18 | 阶段 0 | 容器化骨架、强类型配置、FastAPI 应用与存活检查 | pytest 3 passed、Ruff 通过、Pyright 0 errors、真实 HTTP 返回 status=ok、容器 healthy | Docker Compose、Pydantic Settings、FastAPI 路由、配置缓存与测试隔离 | async 的适用条件、live 与 ready 的边界、TestClient 与真实 HTTP 的测试分层 |
| 2026-07-20 | 阶段 1 | PostgreSQL、异步 ORM、Alembic、知识库 CRUD、统一错误响应 | 空库迁移至唯一 head、10 个单元测试和 5 个集成测试通过、Ruff 与 Pyright 通过、真实 HTTP CRUD 返回 201/200/200/204 | flush、commit、rollback、refresh 与 Service 事务边界 | 完整请求链路、Route/Service/Repository 职责、Engine/连接池/Connection/Session、并发唯一约束、Alembic 与 create_all、单元与集成测试分层 |
| 2026-07-24 | 阶段 2 | Markdown/TXT 字符分块、确定性 Hashing Embedding、余弦检索、进程内知识库隔离、引用回答与最小 RAG API | 31 个单元测试和 8 个集成测试通过、Ruff 与 Pyright 通过、真实 HTTP 创建/摄取/查询/删除返回 201/201/200/204、引用文档 ID 一致 | chunk size 与 overlap 取舍、归一化向量点积、Hashing 与语义 Embedding 的边界、召回与生成问题区分、检索前知识库隔离 | 完整摄取调用链、进程内 Store 的多进程与持久化边界、查询链路中的引用组装细节 |
| 2026-08-09 | 阶段 4 | Milvus standalone Docker、PyMilvus Collection/BM25、Dense+BM25 双路召回、RRF 融合、远程 Embedding/Reranker 客户端、worker 写入 Milvus、retry/delete 清理 Milvus、`/rag/query` 混合检索接线 | `docker compose config --quiet` 通过；Milvus 真实集成测试通过；阶段 4 相关 32 个 unit/integration/e2e 测试通过；外部模型测试默认 skip，待配置真实 key 后运行 `pytest -m external` | Milvus schema/index/BM25 Function、知识库过滤、RRF 不混加原始分、PyMilvus 删除后 flush、默认测试与真实外部 API 验证分层 | 真实 Reranker 服务响应差异、生产 Embedding 维度迁移、LangGraph Agent 如何消费检索证据 |
| 2026-08-09 | 阶段 5 | LangGraph Agent、OpenAI-compatible ChatClient、检索/直答分类、查询改写、最多三次检索循环、PostgreSQL Checkpointer、`/rag/agent/query` 接口 | Chat 客户端单元测试通过；外部 Chat API 测试默认 skip；LangGraph loop-limit 与 direct-answer 测试通过；PostgreSQL checkpoint 真实写入/读回通过；RAG Agent API 集成测试通过 | Agent state/node/edge、工具循环上限、Chat API 边界、SQLAlchemy URL 密码渲染、LangGraph checkpoint 生命周期 | 会话级 thread 复用、SSE token 事件、引用快照落库、真实 Chat 模型提示词稳定性 |
| 2026-08-09 | 阶段 6 | 会话、消息、引用快照 ORM 与迁移；Conversation/Message Repository；会话 REST API；SSE 对话事件；`/conversations/{conversation_id}/messages/stream`；消息插入序号保证刷新后顺序稳定 | `docker compose config --quiet` 通过；主库和测试库迁移到 head；`ruff format --check .` 148 files already formatted；`ruff check .` 通过；`pyright` 0 errors；unit 133 passed；integration 43 passed/3 skipped；E2E 1 passed；external 3 skipped/177 deselected | SSE 事件协议、业务消息与 LangGraph 状态边界、引用快照事务落库、PostgreSQL `now()` 同事务时间戳陷阱、数据库序号排序 | MinerU/PaddleX Docker 解析器、PDF/OCR 版面元数据、Langfuse Trace、评估报告与生产部署收口 |
| 2026-08-09 | 阶段 7 | MinerU/PaddleX Docker profile、统一 `ParsedDocument`、Markdown/TXT/PDF parser router、PDF 上传 parser 选择、解析结果落 MinIO、页码/章节/parser 元数据进入 Milvus 与引用 | `docker compose config --quiet` 通过；主库/测试库迁移到 head；阶段 7 后续全量门禁随阶段 8/9 通过；parser 外部测试默认 skip，配置真实服务后运行 `pytest -m external -v` | 解析器适配层、结构化解析产物、PDF parser 无静默降级、引用元数据可追溯 | 真实 MinerU/PaddleX 镜像的 GPU/CPU 部署差异、复杂扫描件 OCR 质量 |
| 2026-08-09 | 阶段 8 | trace context、结构化 JSON 日志、HTTP `x-trace-id`、Worker/摄取/检索/Agent/SSE 阶段日志、Langfuse SDK 与可选 span、外部测试统一开关 | `ruff format --check .` 190 files already formatted；`ruff check .` 通过；`pyright` 0 errors；unit 160 passed；integration 47 passed/6 skipped；external 6 skipped/208 deselected | 日志上下文、请求/任务 trace、外部测试成本边界、Langfuse 关闭态不影响主链路 | 生产 Langfuse 项目与环境命名、采样率和敏感字段脱敏 |
| 2026-08-09 | 阶段 9 | RAG 评估数据集 schema、Recall@K/MRR/引用命中率、Dense/BM25/RRF/Rerank 对比 Runner、Markdown 报告 CLI、架构/源码/评估/面试交付文档 | 评估单元测试与 integration runner 通过；最终全量门禁记录见阶段 9 进度文档 | 检索评估指标、消融对比、项目表达与面试复盘 | 使用真实业务数据集持续调参、引入 LLM judge 忠实度评估 |

## 5. 当前任务

阶段 0～9 已完成。下一步不再新增主线功能，建议进入真实凭据生产验收：配置 Chat/Embedding/Reranker API、启动 MinerU/PaddleX parser profile、配置 Langfuse，并运行 `pytest -m external -v` 与一组真实 PDF/问答评估数据集。

## 6. 阶段 3 验收记录（2026-08-06）

真实 Docker Compose 环境已验证以下链路：创建知识库，multipart 上传 Markdown 返回 202，ARQ Worker 领取任务并完成解析、分块、Hashing Embedding 和 Redis 索引，API 可下载原文与解析结果；同一已完成任务再次进入 Worker 后 chunk 数量不变；删除后 PostgreSQL 文档记录、MinIO 原文/解析对象和 Redis 索引均不存在。E2E 使用 30 秒固定轮询超时，失败或超时时附带 API 与 Worker 最近日志。

验证证据只记录实际执行结果：独立 Compose project 使用独立端口和命名卷；主数据库与测试数据库均迁移到唯一 Alembic head；`tests/e2e/test_async_ingestion.py` 在真实 API、Worker、PostgreSQL、MinIO、Redis 边界下通过。完整 Ruff、Pyright、unit、integration 结果见阶段 3 进度文档。

### 学习复盘

1. **为什么上传成功用 202，而任务仍可能失败？** 202 只确认 API 已接受请求并完成原文落盘、数据库建档和入队；解析、分块、索引由另一个进程稍后执行，仍可能遇到编码、存储或进程故障。
2. **`flush()`、`commit()`、`rollback()` 分别做什么？** `flush()` 把当前变更发给数据库以获得 ID 或提前触发约束，但事务仍未结束；`commit()` 让事务对其他会话可见；`rollback()` 放弃当前未提交事务，并让 Session 回到可继续使用的状态。
3. **数据库已提交但入队失败时，为什么保留 MinIO 原文？** 文档和失败任务已成为可诊断、可重试的业务事实；保留原文才能人工排障或重新入队，删除它会让数据库记录无法恢复。
4. **Worker 为什么先 claim？** 队列消息可能重复投递或被多个 Worker 同时看到；数据库条件更新只允许一个执行者完成 `pending -> processing`，其余执行者无操作退出。
5. **Redis 文档索引为什么覆盖写而不是追加？** 重试或重复执行必须得到同一份文档级结果；原子 `SET` 覆盖消除旧 chunks，追加会制造重复召回和无法判断的部分版本。
6. **删除为什么不先删数据库？** 数据库记录保存了 MinIO 对象键和 Redis 索引归属；先删记录后外部清理失败会失去补偿依据并留下孤儿数据，所以数据库删除最后提交。
7. **ARQ job 唯一性和数据库任务状态分别解决什么？** 固定 job ID 降低同一任务重复入队；数据库 claim 与状态机处理重复投递、并发执行、进度查询和历史审计。前者不能替代后者。

下一次复习时，请不看代码画出上传、Worker、重试和删除四条数据流，并为每个跨存储步骤说明失败后留下的状态和恢复入口。

## 7. 阶段 4 验收记录（2026-08-09）

真实 Docker Compose 环境已加入 Milvus standalone 三件套：`milvus-etcd`、`milvus-minio` 和 `milvus-standalone`。业务 MinIO 继续保存原文和解析结果，Redis 退回到 ARQ 队列职责，生产文档索引由 Milvus Collection `rag_chunks` 承担。

阶段 4 已验证以下链路：worker 完成解析、分块和 Embedding 后写入 Milvus；Milvus Collection 同时保存 dense vector、BM25 sparse 字段和引用元数据；`/rag/query` 在同一知识库过滤条件下执行 dense 与 BM25 双路召回，使用 RRF 融合候选并调用远程 Reranker 客户端；文档 retry 和 delete 会先清理 Milvus chunk，再处理后续队列、对象存储和数据库状态。

验证证据只记录实际执行结果：Milvus 官方 standalone 拓扑已在 Docker 中启动并通过健康检查；PyMilvus 集成测试证明两个知识库写入同名查询内容时不会串库；端到端测试证明上传、worker 摄取、Milvus 可检索、重复执行幂等、删除后 PostgreSQL/MinIO/Milvus 全部清理。外部 Embedding 与 Reranker 的真实 API 测试已加 `external` 标记，默认跳过；配置真实凭据后使用 `docker compose exec api uv run --no-sync pytest -m external -v` 验证。

### 学习复盘

1. **为什么 Redis 不再适合作生产检索索引？** Redis 阶段只证明跨进程共享索引和任务链路；生产检索需要向量索引、BM25、过滤表达式、批量写入和可维护 schema，这些职责更适合 Milvus。
2. **为什么 Dense 与 BM25 不能直接相加分数？** 两者分数尺度不同，dense 分数通常来自向量距离或相似度，BM25 来自词项统计；直接相加会让某一路尺度主导排序。RRF 使用名次而不是原始分数融合，适合异构召回。
3. **为什么每条 Milvus 查询都带 `knowledge_base_id` 过滤？** 多知识库隔离不能只靠 API 层；索引查询本身必须过滤，否则相同关键词或向量相近的其它知识库文档会被召回。
4. **为什么 delete 后要 flush？** Milvus delete 的可见性不是普通 Python 内存删除；flush 后后续搜索才能稳定看到清理结果，端到端删除验收也因此更可靠。
5. **为什么外部 API 测试默认 skip？** 本地质量门禁应稳定、可重复、不会误消耗额度；真实模型连通性属于显式外部验收，必须由 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 和真实凭据开启。
6. **为什么 worker 保留本地 Hashing fallback？** 这是开发/测试模式的明确安全路径；生产或配置了 API key 时使用真实 OpenAI-compatible EmbeddingClient，避免默认本地测试依赖付费服务。

下一次复习时，请手算一个 dense 排名 `[a,b]` 与 BM25 排名 `[b,c]` 的 RRF 融合结果，并解释为什么 `b` 会排在最前。

## 8. 阶段 5 验收记录（2026-08-09）

阶段 5 已在阶段 4 混合检索基础上接入 LangGraph Agent。Agent 图包含分类、查询改写、检索、证据判断和生成节点；模型通过 OpenAI-compatible Chat API 调用，检索工具复用 `HybridRetrievalService`，图状态通过 PostgreSQL checkpointer 持久化。

阶段 5 已验证以下链路：ChatClient 向 `/chat/completions` 发送 OpenAI-compatible payload 并解析 token usage；Agent 可判断直接回答路径且不调用检索；当模型持续要求更多证据时，图最多执行三次检索并返回证据不足；FastAPI 启动时设置 `LANGGRAPH_STRICT_MSGPACK=true` 并初始化 LangGraph checkpoint 表；真实测试 PostgreSQL 可写入并读回 checkpoint；`/rag/agent/query` 会先校验知识库，再通过 AgentChatService 返回回答和 `[S1]` 引用。

验证证据只记录实际执行结果：checkpoint 集成测试使用 Docker PostgreSQL 真实写入/读回；RAG Agent API 集成测试通过依赖替换验证路由、知识库校验和引用响应结构；外部 Chat API 测试已加 `external` 标记，默认跳过，配置真实凭据后使用 `docker compose exec api uv run --no-sync pytest -m external -v` 验证。

### 学习复盘

1. **为什么 Agent 要先分类是否检索？** 不是所有问题都需要知识库；直接回答可以减少延迟和模型/检索成本，也避免把闲聊类问题硬塞进检索链路。
2. **为什么检索循环必须有硬上限？** LLM 的“还需要更多证据”是模型输出，不是系统不变量；没有上限时会导致无限工具调用、费用失控和请求悬挂。
3. **为什么查询改写独立成节点？** 用户原问题可能包含口语、省略或多意图；检索查询应尽量短、明确、面向召回，而最终回答仍保留原始用户意图。
4. **为什么 checkpoint 使用 PostgreSQL？** 当前业务状态已经在 PostgreSQL 中，checkpoint 同库保存便于事务性运维、备份和后续会话恢复；同时避免为图状态再引入一套额外基础设施。
5. **为什么 SQLAlchemy URL 不能直接 `str()` 后交给 psycopg？** SQLAlchemy 的 `str(URL)` 会隐藏密码；传给真实数据库驱动会导致认证失败，内部连接串必须使用 `render_as_string(hide_password=False)`。
6. **为什么外部 Chat API 测试默认 skip？** 默认质量门禁必须可重复且不消耗额度；真实模型连通性属于显式生产验收，必须由真实凭据和 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 开启。

下一次复习时，请不看代码画出 Agent 图的五个节点，并说明每个节点读取哪些状态、写入哪些状态，以及哪条边阻止无限检索。

## 9. 阶段 6 验收记录（2026-08-09）

阶段 6 已在 LangGraph Agent 基础上补齐会话层。业务状态新增 `conversations`、`messages` 和 `message_citations` 三类持久化对象：会话归属知识库，消息保存 user/assistant 内容、状态、token 统计和数据库生成的插入序号，引用快照保存 document ID、chunk ID、source label、quote、score 与 metadata。

阶段 6 已验证以下链路：客户端可在知识库下创建和列出会话；可查询、删除会话并恢复历史消息；`POST /api/v1/conversations/{conversation_id}/messages/stream` 会先保存用户消息，再通过 Agent 生成回答，以 SSE 事件输出 `message_start`、`agent_status`、`token`、`citation` 和 `message_end`，最后在同一 PostgreSQL 事务里提交 assistant message 与引用快照。引用标签会先与 Agent 返回证据集合校验，不合法引用不会部分落库。

阶段 6 验收过程中发现并修复了一个生产级顺序问题：PostgreSQL 的 `now()` 在同一事务内返回相同时间，user/assistant 两条消息可能拥有相同 `created_at`；若再用随机 UUID 兜底排序，会偶发助手消息排在用户消息前。当前迁移新增 `messages.sequence_number`，由数据库 sequence 生成，消息读取按该序号排序，刷新恢复顺序稳定。

验证证据只记录实际执行结果：`docker compose config --quiet` 通过；主库和测试库均迁移到 Alembic head；`ruff format --check .` 显示 148 files already formatted；`ruff check .` 全部通过；`pyright` 返回 0 errors；`tests/unit` 为 133 passed；`tests/integration` 为 43 passed、3 skipped；`tests/e2e` 为 1 passed；`pytest -m external -v` 为 3 skipped、177 deselected。外部 Chat/Embedding/Reranker 真实 API 入口保留在配置中，当前环境未提供真实凭据时不会误调用付费服务。

### 学习复盘

1. **为什么会话消息要独立于 LangGraph checkpoint？** Checkpoint 保存 Agent 图执行状态，面向恢复和内部编排；业务消息是产品侧可展示、可审计、可分页的数据，两者生命周期和读取方式不同。
2. **为什么引用要落库为快照？** 检索索引和文档解析结果后续可能重建；若只保存 source label，刷新后可能找不到当时回答引用的原文片段。快照让回答可复现。
3. **为什么 SSE 事件要固定名称？** 前端不应解析自然语言状态来判断进度；固定事件名让 UI 可以稳定区分开始、状态、token、引用、结束和错误。
4. **为什么无效引用不能部分落库？** 回答文本和引用必须保持一致；若助手消息已保存但引用失败，用户会看到无法追踪来源的回答，所以引用校验要在 flush 前完成。
5. **为什么不能只按 `created_at` 排消息？** PostgreSQL 的 `now()` 是事务时间，同一事务内多次插入可能完全相同；生产顺序需要数据库生成的单调序号作为可靠依据。
6. **为什么外部 API 测试继续默认 skip？** 默认门禁要可重复、低成本且不依赖凭据；真实生产连通性必须由显式凭据和 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 打开。

下一次复习时，请画出一次 SSE 请求从保存 user message、调用 Agent、输出 token/citation 到提交 assistant message 的事务边界，并解释为什么 message sequence 比 UUID 更适合作排序依据。

## 10. 阶段 7 验收记录（2026-08-09）

阶段 7 已完成 PDF 解析生产化接入。Docker Compose 新增 `parser` profile，下挂 `mineru` 与 `paddlex` 两个解析服务；API/Worker 保持默认主栈可运行，只有需要 PDF 解析时才依赖 parser profile。上传接口支持 multipart `parser` 字段：Markdown/TXT 使用 `local`，PDF 可选 `mineru` 或 `paddlex`，未传时使用 `RAG_AGENT_DEFAULT_PDF_PARSER`。

解析层统一输出 `ParsedDocument`：包含 blocks、page number、section、block index、parser、source filename 等结构化信息。Worker 将解析产物保存到 MinIO 的 `parsed.json`，再按统一结构分块；Milvus chunk schema 与检索/Agent/SSE 引用链路保留页码、章节和 parser 元数据，使普通 PDF 与扫描件 OCR 结果都能追溯到来源。

验收重点是“真实失败可见”：PDF 解析器失败不会静默切换到另一个解析器，任务会进入 failed，错误写入任务和文档状态；外部 MinerU/PaddleX 测试以 `external` 标记保护，默认不会在缺少真实服务时误调用。阶段 7 的代码随后在阶段 8/9 的全量质量门禁中继续通过。

### 学习复盘

1. **为什么要有统一 `ParsedDocument`？** 解析器返回结构各不相同；统一结构让后续分块、索引、引用、评估不关心 PDF 来自 MinerU 还是 PaddleX。
2. **为什么 parser 失败不能自动降级？** 静默降级会掩盖 OCR、版面或服务配置问题，用户看到的引用来源也可能不可复现。生产系统应暴露真实失败并允许人工重试。
3. **为什么页码和章节要进 Milvus metadata？** 检索命中不仅要返回文本，还要能告诉用户证据来自哪一页、哪一节；这些信息必须随 chunk 一起进入索引。

## 11. 阶段 8 验收记录（2026-08-09）

阶段 8 建立了生产质量和可观测性基础。API 中间件支持 `x-trace-id` 透传和自动生成，响应头返回同一 trace ID；Worker 使用 task ID 建立任务级 trace；摄取、解析、分块、向量化、索引、混合检索、重排、Agent 和 SSE 都会写入阶段日志。

结构化日志使用 JSON formatter，稳定包含 `trace_id`、`stage`、`knowledge_base_id`、`document_id`、`task_id`、`conversation_id`、`message_id`、`parser`、`retrieval_attempt` 等上下文。为了兼容既有业务日志 `extra`，LogRecord 上使用安全前缀保存上下文字段，同时 JSON 输出保持原字段名。

Langfuse SDK 已作为正式依赖加入；当 `RAG_AGENT_LANGFUSE_BASE_URL`、`RAG_AGENT_LANGFUSE_PUBLIC_KEY`、`RAG_AGENT_LANGFUSE_SECRET_KEY` 配置完整时，核心链路会导出 span；未配置时 tracer 自动关闭，不影响本地开发、CI 或默认测试。真实外部服务测试由 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 显式打开。

验证证据：`docker compose config --quiet` 通过；主库和测试库均迁移到 Alembic head；`ruff format --check .` 显示 190 files already formatted；`ruff check .` 全部通过；`pyright` 返回 0 errors；unit 为 160 passed；integration 为 47 passed、6 skipped；E2E 为 1 passed；external 为 6 skipped、208 deselected。

### 学习复盘

1. **为什么 trace ID 要从 HTTP 到 Worker 分开处理？** HTTP 请求和异步任务生命周期不同；API 用请求 trace，Worker 用 task ID，可分别定位同步入口和后台执行。
2. **为什么外部测试默认跳过？** 默认门禁必须稳定、低成本、可重复；真实服务连通性是显式生产验收，不应在没有凭据时消耗额度或失败。
3. **为什么日志字段要避免覆盖业务 `extra`？** 业务日志可能已经带 `document_id`、`task_id`；观测层不能因为注入上下文导致原本的错误处理日志崩溃。

## 12. 阶段 9 验收记录（2026-08-09）

阶段 9 完成可复现评估与求职交付材料。`app/evaluation` 定义评估数据集 schema、检索指标、评估 Runner 和 Markdown 报告生成器；`scripts/run_evaluation.py` 可在 Docker 环境中读取 JSON/YAML 数据集，对 Dense、BM25、RRF、Rerank 四种模式计算 Recall@K、MRR 与 citation hit rate，并输出报告。

文档交付包括架构说明、源码导读、Yuxi 对照、评估使用说明和面试材料。所有材料只描述仓库中已经实现并通过测试的能力，避免把计划中未做的 judge faithfulness、生产网关、权限系统等包装成已完成能力。

最终定位：该项目已从“教学 RAG demo”收口到“可本地 Docker 启动、可接真实模型 API、可接 PDF 解析服务、可观测、可评估、可复盘”的生产化后端样板。下一步工作应围绕真实业务数据集、真实外部凭据、部署安全和性能压测，而不是继续扩主线功能。

### 学习复盘

1. **为什么评估要同时看 Dense、BM25、RRF 和 Rerank？** 单一路径只能证明某种召回方式有效；对比四种模式才能解释混合检索和重排是否真的带来收益。
2. **为什么 citation hit rate 不等同于答案正确？** 它只衡量引用命中了预期证据，不能证明模型回答忠实；后续可引入人工标注或 LLM judge 作为补充。
3. **为什么求职材料必须只写已验证能力？** 面试追问会落到实现细节、失败恢复和测试证据；真实完成的能力更容易讲清楚，也更抗追问。
