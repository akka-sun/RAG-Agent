# 阶段 7 进度记录：PDF 解析器与结构化摄取

日期：2026-08-09

## 完成范围

- Docker Compose 新增 `parser` profile，配置 MinerU 与 PaddleX 服务入口。
- `.env.example` 新增 MinerU/PaddleX 镜像、端口、pipeline、device 和默认 PDF parser 配置。
- 新增统一 `ParsedDocument`/`ParsedBlock` 类型，Markdown、TXT、MinerU PDF、PaddleX PDF 统一归一化。
- 上传接口支持 `.pdf`，并通过 multipart `parser` 字段选择 `mineru` 或 `paddlex`。
- Worker 将解析结果保存为结构化 JSON，并将 page、section、parser、block index 写入 chunk metadata。
- Milvus、检索响应、Agent evidence、SSE citation 均保留 PDF 来源元数据。

## 真实服务边界

- Milvus 以 Docker 服务运行，并在集成/E2E 中真实验证。
- MinerU/PaddleX 以 Docker profile 提供生产入口：`docker compose --profile parser up -d mineru paddlex`。
- Parser 外部测试默认跳过；只有配置真实服务并设置 `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true` 才会实跑。
- PDF 解析失败不会自动 fallback，便于暴露真实部署或 OCR/版面问题。

## 验收结果

- `docker compose config --quiet`：通过。
- 主库和测试库 Alembic migration：升级到 head。
- 阶段 7 相关单元、集成、E2E 测试在后续全量门禁中持续通过。
- `pytest -m external -v`：parser 外部测试默认 skip，等待真实 MinerU/PaddleX 服务和凭据/地址。

## 下一阶段

进入阶段 8：工程质量与可观测性，补齐 trace、结构化日志、Langfuse 和外部测试门禁。

