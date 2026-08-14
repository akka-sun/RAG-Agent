# 固定嵌入配置与基础设施就绪检测设计

## 目标

消除知识库级嵌入参数与系统真实运行配置不一致的风险，并让状态页展示后端依赖的真实可用性，而不是根据 API 存活状态推断基础设施状态。

## 方案选择

采用以下方案：

1. **推荐：全局固定配置 + 聚合 readiness 接口。** 后端是嵌入模型和维度的唯一事实来源；状态页只调用后端聚合接口。边界清晰，适合当前单一 Milvus Collection 和单一 Embedding Client 的架构。
2. **保留知识库级配置。** 需要按知识库创建不同维度的 Collection、动态构造客户端并处理模型迁移，明显超出当前架构需求，不采用。
3. **前端读取 Docker 状态。** 浏览器无法安全、可移植地访问 Docker Engine，也不适用于非 Docker 部署，不采用。

## 固定嵌入配置

- `RAG_AGENT_EMBEDDING_MODEL` 与 `RAG_AGENT_EMBEDDING_DIMENSION` 继续作为全局配置；当前运行值为 `Qwen/Qwen3-Embedding-8B` 和 `4096`。
- 创建知识库的前端表单只收集名称和描述，不再允许输入模型或维度。
- 后端 `POST /api/v1/knowledge-bases` 的创建请求只接收 `name`、`description`。服务层从 `Settings` 注入 `embedding_model`、`embedding_dimension` 后持久化，客户端无法覆盖。
- 知识库响应继续返回模型和维度，详情页和卡片以只读方式展示，方便审计已有数据。
- 不自动迁移已有知识库向量；当前测试数据已清空。未来若更换全局模型或维度，应通过独立重建索引流程完成，不能直接修改现有 Collection 的维度。

## 健康与就绪接口

- 保留 `GET /api/v1/health/live`，只表示 API 进程存活，继续快速返回 `{ "status": "ok" }`。
- 新增 `GET /api/v1/health/ready`，由后端分别探测：
  - PostgreSQL：执行 `SELECT 1`。
  - Redis：执行 `PING`。
  - MinIO：检查目标 Bucket 是否存在且可访问。
  - Milvus：连接服务并确认配置的 Collection 可访问；检测不得创建或修改 Collection。
- 每项返回 `status`（`healthy` 或 `unhealthy`）、`latency_ms` 和可选的中文安全错误信息。响应不包含密码、连接串、Token、主机内部堆栈。
- 顶层 `status`：全部健康时为 `ok`，任一依赖失败时为 `degraded`。即使 degraded，接口仍返回 HTTP 200，以便状态页稳定展示每项结果；API 自身无法执行检测时才返回统一的 HTTP 500。
- 各探测设置短超时并相互独立、并发执行；单项失败不能阻止其他结果返回。

示例：

```json
{
  "status": "ok",
  "services": {
    "postgresql": { "status": "healthy", "latency_ms": 3 },
    "redis": { "status": "healthy", "latency_ms": 1 },
    "minio": { "status": "healthy", "latency_ms": 5 },
    "milvus": { "status": "healthy", "latency_ms": 8 }
  }
}
```

## 前端状态页

- 继续显示前端和 API liveness。
- 额外请求 readiness 并为 PostgreSQL、Redis、MinIO、Milvus 分别展示健康状态与延迟。
- `degraded` 时保留已成功服务的绿色状态，仅对失败服务展示红色状态和后端返回的安全错误。
- “重新检查”同时刷新 liveness 与 readiness；请求进行中禁止重入；卸载或新请求产生后忽略旧响应。
- readiness 接口整体不可达时，基础设施统一显示“无法检测”，但不伪装为服务故障。

## 测试与验收

- 后端测试证明客户端不能提交/覆盖嵌入模型与维度，且持久化值来自 Settings。
- 后端 readiness 测试覆盖全部健康、单项失败、超时、错误信息脱敏和探测互不影响。
- 前端测试证明创建表单不再出现模型/维度输入，提交体只含名称和描述。
- 状态页测试覆盖全部健康、部分降级、整体不可检测、重试、防重入和陈旧响应隔离。
- 运行后端相关测试、前端全量测试、类型检查、生产构建，并通过真实 Compose 环境验证四项依赖均为 healthy。

## 非目标

- 不支持每个知识库选择不同嵌入模型或向量维度。
- 不在本次实现模型切换后的向量重建向导。
- 不向浏览器暴露 Docker Socket、数据库凭据或内部连接信息。
