# Task 10 实施报告：E2E 工作流与最终验证

日期：2026-08-14

工作树：`D:\OneDrive\文档\RAG Agent\RAG-Agent\.worktrees\rag-agent-frontend`

分支：`codex/rag-agent-frontend`

目标提交：`test(frontend): cover complete RAG workflow`

## 实施范围

- 新增 Playwright 配置，全部项目使用 Chromium：
  - desktop：1440×900
  - tablet/browser QA：768×900
  - mobile：390×844
- 新增每测试隔离、可变状态的 `/api/v1/**` route fixture。
- 新增完整 RAG 旅程、确定性失败重试、状态页与深链刷新三个 E2E。
- README 补充一条命令启动完整 Compose 栈及最终前端测试命令。
- 仅修复 E2E 证实的三个真实 UI/工作流缺陷：
  1. 文档/摄取状态原样显示后端英文枚举；改为中文用户标签。
  2. `/chat` 没有客户端路由；为现有 chat route 增加 alias。
  3. 引用详情 dialog 的 accessible name 是文件名；改为“引用来源”，文件名保留为正文元数据。
- Vitest 明确排除 `e2e/**`，避免 Playwright spec 被单元测试运行器误收集；两个既有展示断言同步到中文用户标签。

## Fixture 设计与契约覆盖

`frontend/e2e/fixtures.ts` 在 `page` 首次使用前拦截同源 `**/api/v1/**`，未匹配请求返回 501，并在 fixture teardown 断言 unknown request 列表为空，因此不会静默调用真实 API。

每个测试获得独立状态：

- `knowledgeBases`、`documents`、`conversations` 使用可变数组。
- ingestion task 与 polling 次数使用 per-test `Map`。
- persisted messages 使用 conversation ID 到 message pair 的 `Map`。
- 删除知识库会同步移除其文档和会话；删除文档/会话会影响后续 list/get。
- 提供 `seedCompleteWorkflow()` 和 `failNextStream()`，仅用于测试 fixture，不进入生产代码。

契约响应：

- Knowledge bases：list/create/get/delete；create 回显 `text-embedding-3-small` 与 `1536`。
- Documents：list/upload/get/delete/retry/task；upload 返回 202 与固定 document/task UUID。
- Task progression：第 1、2、3 次 polling 依次返回 `pending → processing → completed`；completed 后文档 list 返回 `chunk_count: 1`。
- Conversations：list/create/get/messages/delete，创建/删除都会更新后续列表。
- Health：`GET /api/v1/health/live` 返回 `{ "status": "ok" }`。
- SSE：`POST /conversations/{id}/messages/stream` 返回 `text/event-stream`，包含 `message_start`、`agent_status`、3 个 token、citation、`message_end`。
- Stream 成功前写入 fixture 的 persisted message pair；随后真实 UI 触发 messages GET，返回 completed user/assistant pair 及 citation snapshot（filename、document ID、chunk ID、quote、section、page、score）。
- 失败重试测试第一次 SSE 返回确定性 error event，第二次返回完整成功序列。

## E2E 旅程

完整旅程从 `/knowledge-bases` 空状态开始：

1. 创建“产品资料库”，model=`text-embedding-3-small`，dimension=`1536`。
2. 进入文档页，使用内存文件上传 `sample.md`，内容为 `# 保修政策\n产品保修期为两年`。
3. 观察“处理中”与“处理完成”，再确认 table 中的 `sample.md`。
4. 通过可访问导航打开新对话，创建“保修政策咨询”。
5. 显式检查会话轨道：桌面持续可见，768/390 覆盖打开与关闭 overlay。
6. 发送“产品保修多久？”，检查流式完成后的 authoritative persisted answer `产品保修期为两年 [S1]。`。
7. 点击 `查看引用 S1`，在 accessible dialog `引用来源` 中检查 quote、`sample.md`、精确 document UUID 与 chunk ID。
8. 每个视口检查 document root `scrollWidth - innerWidth <= 1`，防止全页横向溢出。

第二个测试覆盖 SSE error 后 `生成失败：模拟流式失败`、`重试上一条消息`、第二次成功与恰好两次 stream attempt。

第三个测试覆盖：

- PostgreSQL/Redis/MinIO/Milvus 四项均显示“后端未提供检测接口”。
- `/chat` 首次直达和 reload 均渲染 chat 页面。
- `/knowledge-bases/{id}` 首次直达和 reload 均渲染文档页面。

## 红绿记录

### 测试基础设施红灯

1. 第一次 Playwright 调用在 browser launch 前失败：本机缺少 `chromium_headless_shell-1234`；移动设备预设还默认选择 WebKit。
2. 将移动 project 显式设为 `browserName: chromium`。
3. `pnpm test:e2e:install` 成功安装 Playwright Chromium 151、Chromium headless shell、FFmpeg 与 Winldd。
4. 受限 sandbox 内 browser launch 报 `spawn EPERM`；按权限规范提升只读测试运行权限后开始获得真实 UI 断言结果。

### 首个真实 UI 红灯

命令：`pnpm test:e2e --project=desktop-chromium --workers=1`

- 1 passed：确定性失败重试。
- 2 failed：
  - 完整旅程找不到“处理中”；accessibility snapshot 显示 task/table 使用 raw `completed`。
  - `/chat` HTTP 壳层 200，但 router view 为空，找不到 heading“新对话”。

最小修复后，完整旅程继续暴露第二个真实 accessibility 红灯：引用 dialog 的 accessible name 是 `sample.md`，不是“引用来源”。调整 dialog 标题语义后 desktop 3/3 通过。

期间有一次非产品红灯：“处理完成”同时出现在进度区与文档 table，locator strict-mode 歧义；测试改为使用 accessible region“摄取任务”限定范围，未改 UI。

### 绿灯

- Desktop targeted：3/3 passed。
- Mobile targeted：3/3 passed。
- Tablet/browser QA targeted：3/3 passed。
- 最终全部 projects 并行：9/9 passed（21.8s）。

## 视觉 / 浏览器 QA

真实 Chromium 渲染矩阵运行完整旅程：1440×900、768×900、390×844。检查结果：

- 主导航：桌面侧栏持续可见；390 宽度通过 hamburger 打开后可访问导航链接并在跳转后关闭。
- Chat rail：1440 可见；768/390 显式打开、焦点可达并通过 overlay 关闭。
- Composer：三档宽度均可通过 label“输入消息”和 button“发送”完成提交；移动端 actions 未造成全页 overflow。
- Citation sheet：1440 为右侧 drawer；390 CSS bottom sheet 路径由相同 dialog/内容断言覆盖；精确 metadata 可见。
- Tables/upload progress：完成上传、processing/completed 文案、文档 table 以及 table 内部横向滚动容器；三档均无 document-level 横向溢出。
- Create dialog 与 status cards：三档均由可访问 role/name 定位并完成交互/断言。
- 成功运行未保留截图或 trace；失败期产物位于 gitignored 目录，后续成功运行已清理 failure artifacts。

尝试使用 Codex in-app browser 做额外人工面板检查时，宿主运行时因 `EPERM: lstat C:\Users\DELL\AppData` 无法连接。该工具限制未影响真实 Playwright Chromium 三档渲染与 DOM/交互 QA，作为 concern 保留。

## 最终命令与结果

在 `frontend/`：

- `pnpm test:run`：21 test files passed，120 tests passed，exit 0。
- `pnpm typecheck`：exit 0，无 TypeScript/Vue 错误。
- `pnpm build`：119 modules transformed，生产构建 exit 0；JS bundle 161.29 kB（gzip 57.34 kB）。
- `pnpm test:e2e`：desktop/tablet/mobile 共 9 tests passed，exit 0，21.8s。

在仓库根目录：

- `docker compose config --quiet`：exit 0。
- 当前工作树默认 Compose project 下没有已启动容器；现有服务属于 project `rag-agent`。
- `docker compose -p rag-agent ps frontend api`：
  - `rag-agent-api-1`：Up (healthy)，host `127.0.0.1:8001`。
  - `rag-agent-frontend-1`：Up (healthy)，host `127.0.0.1:5173`。
- `GET http://127.0.0.1:5173/api/v1/health/live`：`{"status":"ok"}`。
- `GET http://127.0.0.1:5173/chat`：HTTP 200，`Content-Type: text/html`。

没有停止容器、删除容器或删除 Docker volume。

## Git 卫生与安全

- `.gitignore` 新增 `frontend/test-results/` 与 `frontend/playwright-report/`。
- fixture 只包含固定 UUID 与虚构内容；未使用或输出真实 secret。
- 提交前执行 `git diff --check`、`git status --short` 和变更文件/敏感值检查。
- 只暂存 Task 10 文件；其他 Task report/brief/progress 的既有未提交内容保持不动。

## Concerns

- Codex in-app browser 额外面板检查被宿主 AppData 权限阻断；真实 Chromium 三档 E2E 已覆盖要求的视觉结构与交互，且全部通过。
- fixture 的 SSE body 由 route fulfillment 一次性交付，但包含完整、有序的多个 SSE event；真实前端 parser、reducer、消息持久化 refresh 路径均被执行。网络分块边界已由既有 SSE 单元测试覆盖。
- 本任务按要求未扩展处理 Task 3/6/7/9 deferred minor；本轮 E2E 没有证明它们是 load-bearing 阻塞。
