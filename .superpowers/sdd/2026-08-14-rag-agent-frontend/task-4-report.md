# Task 4 实施报告

## 状态

完成。文档上传、PDF 解析器选择、摄取任务轮询、终态刷新、文档列表、重试/确认删除、原文与解析结果下载、安全预览及资源清理均已实现。

## 文件

- `frontend/src/stores/documents.ts`
- `frontend/src/stores/documents.spec.ts`
- `frontend/src/components/documents/DocumentUploader.vue`
- `frontend/src/components/documents/DocumentUploader.spec.ts`
- `frontend/src/components/documents/DocumentTable.vue`
- `frontend/src/components/documents/IngestionProgress.vue`
- `frontend/src/components/documents/DocumentPreview.vue`
- `frontend/src/pages/KnowledgeBaseDetailPage.vue`

## TDD 红绿证据

- RED 1：focused test 首次运行，2 个 suite 因 `documents` store 与文档组件不存在而失败。
- GREEN 1：实现验证、fake-timer 轮询与安全预览后，focused tests 10/10 通过。
- RED 2：移除未获测试保护的 parser 转发、retry/remove，并加入表格/进度测试后，3 个 store 测试及 1 个缺失组件 suite 按预期失败。
- GREEN 2：最小恢复 parser 转发、retry/remove、表格和进度组件后，focused tests 15/15 通过。
- RED 3：详情页装配测试因未加载路由知识库而失败（1/8）。
- GREEN 3：装配详情页加载、管理与卸载清理后，focused tests 16/16 通过。

## 命令与结果

- `pnpm test:run src/stores/documents.spec.ts src/components/documents/DocumentUploader.spec.ts`：2 files、16 tests 通过。
- `pnpm test:run`：6 files、35 tests 通过。
- `pnpm typecheck`：通过，退出码 0。
- `pnpm build`：通过，81 modules transformed，退出码 0。
- `git diff --check`：通过。

注：Codex bundled Node 未在子进程 PATH 中，验证命令执行前显式加入其 Node `bin` 目录；未改变项目配置。

## 提交

- `feat(frontend): add document ingestion workspace`

## 自审

- 轮询使用 1s、2s、3s、4s、5s 后封顶 5s；终态只刷新一次。
- 连续网络失败第五次后停止并给出刷新重试提示；成功响应会重置连续失败计数。
- 页面卸载、store dispose、显式停止及终态均清理计时器/AbortController。
- 预览没有 `v-html`/`innerHTML`；文本由 Vue 转义，PDF 使用浏览器原生 object。
- 图片请求只来自解析 JSON 中合法的 `asset_index`，没有猜测索引探测。
- 预览、图片与下载使用的对象 URL 均有撤销路径。
- 未暂存或修改 Task 4 之外的既有用户文件。

## Concerns

- 未做连接真实后端与对象存储的手工浏览器 smoke test；API 边界、生命周期和构建由自动化测试覆盖。
