# 阶段 8 进度记录：工程质量与可观测性

日期：2026-08-09

## 完成范围

- 新增 `app/observability`：trace context、结构化 JSON logging、Langfuse tracer。
- API 支持 `x-trace-id` 透传；未传时自动生成，并在响应头返回。
- Worker 使用 task ID 建立任务 trace。
- 摄取、解析、分块、向量化、索引、检索、重排、Agent、SSE 关键阶段写入日志上下文。
- Langfuse SDK 已加入依赖；配置完整时导出 span，未配置时自动关闭。
- 新增外部测试统一开关：`RAG_AGENT_EXTERNAL_TESTS_ENABLED=true`。
- `.gitignore` 忽略本地虚拟环境、Python 缓存和测试缓存。

## 验收结果

- `ruff format --check .`：190 files already formatted。
- `ruff check .`：All checks passed。
- `pyright`：0 errors, 0 warnings, 0 informations。
- `pytest tests/unit -v`：160 passed。
- `pytest tests/integration -v`：47 passed、6 skipped。
- `pytest tests/e2e -v`：1 passed。
- `pytest -m external -v`：6 skipped、208 deselected，避免误调用真实外部服务。

## 关键设计

- 日志 JSON 保持业务字段名；LogRecord 属性使用安全前缀，避免和业务 `extra` 撞名。
- Langfuse 是“生产增强能力”，不是默认运行依赖；缺少配置时不会影响主链路。
- 外部服务测试与默认质量门禁分层，既能真实验收，也不会让本地 CI 依赖付费服务。

## 下一阶段

进入阶段 9：补齐评估 Runner、报告、最终架构说明、源码导读和面试材料。
