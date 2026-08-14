# RAG Agent Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready Vue frontend that exposes every implemented RAG Agent backend workflow through a chat-first browser experience.

**Architecture:** A standalone Vue 3 SPA owns browser state and talks only to same-origin `/api/v1`. Vite proxies API traffic in development; an Nginx container serves the production bundle, falls back to `index.html` for client routing, and proxies `/api/v1` to FastAPI. Pinia stores separate persisted resources from transient SSE and upload-task state.

**Tech Stack:** Vue 3, TypeScript, Vite, Pinia, Vue Router, Vitest, Vue Test Utils, Playwright, Nginx, Docker Compose

## Global Constraints

- The UI is Chinese-first and light-theme only.
- Default browser URL is `http://127.0.0.1:5173`.
- All browser API calls use `/api/v1`; do not add backend CORS middleware.
- Supported uploads are non-empty `.md`, `.txt`, and `.pdf` files no larger than 5 MiB.
- PDF parser values are exactly `mineru` and `paddlex`; text documents use `local` or omit the parser.
- Never display fabricated metrics or infrastructure health states.
- Do not add authentication, knowledge graphs, MCP, Skills, model settings, conversation rename, or dark mode.
- Keep UUID values as TypeScript `string` values.
- Use test-driven development and commit after every task.

---

## File Map

- `frontend/src/api/client.ts`: JSON, multipart, Blob, and normalized API errors.
- `frontend/src/api/sse.ts`: fetch-based POST SSE parser with abort support.
- `frontend/src/api/resources.ts`: typed backend endpoint functions.
- `frontend/src/types/api.ts`: backend DTOs and SSE event unions.
- `frontend/src/stores/knowledge-bases.ts`: knowledge-base collection and selection.
- `frontend/src/stores/conversations.ts`: conversations and persisted messages.
- `frontend/src/stores/chat.ts`: transient streaming message and event state.
- `frontend/src/stores/documents.ts`: documents, upload tasks, and polling.
- `frontend/src/components/`: focused reusable navigation, feedback, upload, message, citation, and dialog units.
- `frontend/src/pages/`: route-level orchestration only.
- `frontend/src/styles/`: tokens, base styles, layout, and responsive rules.
- `frontend/nginx.conf`: SPA fallback and API reverse proxy.
- `frontend/Dockerfile`: production frontend image.
- `docker-compose.yml`: frontend service and port 5173.

### Task 1: Frontend foundation and application shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/layouts/AppShell.vue`
- Create: `frontend/src/components/navigation/AppSidebar.vue`
- Create: `frontend/src/pages/ChatPage.vue`
- Create: `frontend/src/pages/KnowledgeBasesPage.vue`
- Create: `frontend/src/pages/KnowledgeBaseDetailPage.vue`
- Create: `frontend/src/pages/ConversationsPage.vue`
- Create: `frontend/src/pages/StatusPage.vue`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/base.css`
- Create: `frontend/src/styles/layout.css`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/components/navigation/AppSidebar.spec.ts`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: none.
- Produces: route names `chat`, `knowledge-bases`, `knowledge-base-detail`, `conversations`, `status`; a mounted Pinia instance; `AppShell` with `<router-view />`.

- [ ] **Step 1: Create package and test configuration**

Use scripts `dev`, `build`, `typecheck`, `test`, `test:run`, and `test:e2e`. Pin exact compatible major lines: Vue 3, Vite 7, Pinia 3, Vue Router 4, Vitest 3, Vue Test Utils 2, Playwright 1, TypeScript 5.

- [ ] **Step 2: Write the failing navigation test**

```ts
it('renders all implemented product areas', () => {
  const wrapper = mount(AppSidebar, { global: { plugins: [router] } })
  expect(wrapper.text()).toContain('新对话')
  expect(wrapper.text()).toContain('会话')
  expect(wrapper.text()).toContain('知识库')
  expect(wrapper.text()).toContain('文档')
  expect(wrapper.text()).toContain('系统状态')
})
```

- [ ] **Step 3: Run the focused test and verify failure**

Run: `cd frontend; npm install; npm run test:run -- src/components/navigation/AppSidebar.spec.ts`

Expected: FAIL because `AppSidebar.vue` and router do not exist.

- [ ] **Step 4: Implement the shell, routes, and light design tokens**

Create the five named routes. Make “新对话” navigate to `{ name: 'chat', query: { new: '1' } }`; make “文档” navigate to the selected knowledge-base detail when available and otherwise to `knowledge-bases`. Define light tokens for page, surface, sidebar, text, muted text, border, indigo action, success, warning, and destructive states. Add keyboard-visible focus styles and responsive sidebar collapse.

- [ ] **Step 5: Verify foundation**

Run: `cd frontend; npm run test:run; npm run typecheck; npm run build`

Expected: all commands pass and `frontend/dist/index.html` exists.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore frontend
git commit -m "feat(frontend): scaffold Vue application shell"
```

### Task 2: Typed API client and backend contracts

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/resources.ts`
- Create: `frontend/src/api/client.spec.ts`
- Create: `frontend/src/api/resources.spec.ts`

**Interfaces:**
- Consumes: `/api/v1` backend routes from `app/api/routes`.
- Produces: `ApiError`, `apiJson<T>()`, `apiBlob()`, `knowledgeBasesApi`, `documentsApi`, `conversationsApi`, `healthApi`, and DTO interfaces matching Pydantic fields exactly.

- [ ] **Step 1: Define DTOs from backend schemas**

Include `KnowledgeBase`, `KnowledgeBaseCreate`, `DocumentRecord`, `DocumentAccepted`, `IngestionTask`, `Conversation`, `Message`, `MessageCitation`, `HealthResponse`, and `ErrorResponse`. Use the exact task status union:

```ts
export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'
```

- [ ] **Step 2: Write failing client tests**

```ts
it('normalizes structured backend errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ error: { code: 'document_too_large', message: 'too large' } }),
    { status: 413, headers: { 'content-type': 'application/json' } },
  )))
  await expect(apiJson('/documents')).rejects.toMatchObject({
    status: 413, code: 'document_too_large', message: 'too large',
  })
})
```

Also test a non-JSON 502 response and a successful 204 response.

- [ ] **Step 3: Run tests and verify failure**

Run: `cd frontend; npm run test:run -- src/api/client.spec.ts src/api/resources.spec.ts`

Expected: FAIL because client exports do not exist.

- [ ] **Step 4: Implement the generic client and resource APIs**

`apiJson<T>` must set JSON headers only when a JSON body exists, preserve `FormData` boundaries, accept `AbortSignal`, return `undefined` for 204, and throw `ApiError`. Resource functions must use encoded path parameters and expose all implemented endpoints, including document source/parsed/image URLs and retry.

- [ ] **Step 5: Verify API layer**

Run: `cd frontend; npm run test:run -- src/api; npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/api frontend/src/types
git commit -m "feat(frontend): add typed backend API client"
```

### Task 3: Knowledge-base state and management page

**Files:**
- Create: `frontend/src/stores/knowledge-bases.ts`
- Create: `frontend/src/stores/knowledge-bases.spec.ts`
- Create: `frontend/src/components/knowledge-base/KnowledgeBaseCard.vue`
- Create: `frontend/src/components/knowledge-base/KnowledgeBaseForm.vue`
- Create: `frontend/src/components/common/ConfirmDialog.vue`
- Create: `frontend/src/components/common/EmptyState.vue`
- Create: `frontend/src/components/common/InlineAlert.vue`
- Modify: `frontend/src/pages/KnowledgeBasesPage.vue`
- Modify: `frontend/src/layouts/AppShell.vue`

**Interfaces:**
- Consumes: `knowledgeBasesApi.list/create/remove`.
- Produces: `useKnowledgeBaseStore()` with `items`, `selectedId`, `selected`, `loading`, `error`, `load()`, `select(id)`, `create(input)`, and `remove(id)`.

- [ ] **Step 1: Write failing store tests**

Test that `select(id)` persists `rag-agent:selected-kb` to localStorage, rejects stale IDs after `load()`, and selects the first available knowledge base when no valid selection exists.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend; npm run test:run -- src/stores/knowledge-bases.spec.ts`

Expected: FAIL because the store does not exist.

- [ ] **Step 3: Implement store and management components**

The create form must require a nonblank name/model and positive integer dimension. The delete dialog must state that documents, conversations, and indexes will be removed. Knowledge-base cards show only actual backend fields plus a document count only when the page has loaded that list.

- [ ] **Step 4: Wire the page and global selector**

Load on entry, show loading/empty/error states, open the creation dialog, navigate to detail after creation, update global selection, and return to a valid selection after deletion.

- [ ] **Step 5: Verify feature**

Run: `cd frontend; npm run test:run; npm run typecheck; npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/stores frontend/src/components frontend/src/pages frontend/src/layouts
git commit -m "feat(frontend): add knowledge base management"
```

### Task 4: Document upload, ingestion polling, and document management

**Files:**
- Create: `frontend/src/stores/documents.ts`
- Create: `frontend/src/stores/documents.spec.ts`
- Create: `frontend/src/components/documents/DocumentUploader.vue`
- Create: `frontend/src/components/documents/DocumentTable.vue`
- Create: `frontend/src/components/documents/IngestionProgress.vue`
- Create: `frontend/src/components/documents/DocumentPreview.vue`
- Create: `frontend/src/components/documents/DocumentUploader.spec.ts`
- Modify: `frontend/src/pages/KnowledgeBaseDetailPage.vue`

**Interfaces:**
- Consumes: `documentsApi.list/upload/task/retry/remove/sourceUrl/parsedUrl/imageUrl`.
- Produces: `useDocumentStore()` with `documentsByKnowledgeBase`, `tasks`, `load(kbId)`, `upload(kbId,file,parser?)`, `pollTask(taskId)`, `retry(kbId,documentId)`, `remove(kbId,documentId)`, and `stopAllPolling()`.

- [ ] **Step 1: Write failing validation and polling tests**

```ts
expect(validateUpload(new File([], 'empty.md'))).toBe('文件不能为空')
expect(validateUpload(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.pdf')))
  .toBe('文件不能超过 5 MiB')
expect(validateUpload(new File(['x'], 'notes.docx'))).toBe('仅支持 .md、.txt 和 .pdf')
```

Use fake timers to verify polling stops at `completed` and refreshes the document list exactly once.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend; npm run test:run -- src/stores/documents.spec.ts src/components/documents/DocumentUploader.spec.ts`

Expected: FAIL because validation and store do not exist.

- [ ] **Step 3: Implement upload and bounded polling**

Use multipart fields `file` and optional `parser`. For `.pdf`, require an explicit `mineru` or `paddlex` selection in the UI. Poll known tasks at 1 second, then 2, 3, and a maximum 5-second interval; stop on unmount, abort, `completed`, or `failed`. Retry transient network failures at most five consecutive times and then expose an actionable error.

- [ ] **Step 4: Implement table, preview, retry, download, and deletion**

Show filename, parser, size, status, chunk count, update time, and backend error. Use Blob/object URLs for safe text/JSON preview, browser-native PDF embedding with a download fallback, and escaped text rendering. Offer parsed images only when the parsed payload exposes asset indexes; do not guess indexes.

- [ ] **Step 5: Verify feature**

Run: `cd frontend; npm run test:run; npm run typecheck; npm run build`

Expected: PASS and no timer remains after component unmount tests.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/stores/documents.ts frontend/src/stores/documents.spec.ts frontend/src/components/documents frontend/src/pages/KnowledgeBaseDetailPage.vue
git commit -m "feat(frontend): add document ingestion workspace"
```

### Task 5: Conversation management and persisted messages

**Files:**
- Create: `frontend/src/stores/conversations.ts`
- Create: `frontend/src/stores/conversations.spec.ts`
- Create: `frontend/src/components/conversations/ConversationList.vue`
- Create: `frontend/src/components/conversations/ConversationCreateDialog.vue`
- Modify: `frontend/src/pages/ConversationsPage.vue`
- Modify: `frontend/src/pages/ChatPage.vue`

**Interfaces:**
- Consumes: `conversationsApi.list/create/get/remove/messages` and `useKnowledgeBaseStore()`.
- Produces: `useConversationStore()` with `itemsByKnowledgeBase`, `messagesByConversation`, `currentId`, `loadForKnowledgeBase(kbId)`, `create(kbId,title)`, `select(id)`, `loadMessages(id)`, and `remove(id)`.

- [ ] **Step 1: Write failing conversation store tests**

Test knowledge-base-scoped caching, chronological message ordering, selection after create, and clearing current selection after delete.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend; npm run test:run -- src/stores/conversations.spec.ts`

Expected: FAIL because the store does not exist.

- [ ] **Step 3: Implement store and management UI**

Use title length 1–200, never expose rename, and only display message count after messages have actually loaded. The chat route uses `?conversation=<uuid>` for selected conversation and `?new=1` for the create flow.

- [ ] **Step 4: Verify feature**

Run: `cd frontend; npm run test:run; npm run typecheck; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/conversations.ts frontend/src/stores/conversations.spec.ts frontend/src/components/conversations frontend/src/pages
git commit -m "feat(frontend): add conversation management"
```

### Task 6: POST SSE parser and streaming chat state

**Files:**
- Create: `frontend/src/api/sse.ts`
- Create: `frontend/src/api/sse.spec.ts`
- Create: `frontend/src/stores/chat.ts`
- Create: `frontend/src/stores/chat.spec.ts`

**Interfaces:**
- Consumes: `POST /api/v1/conversations/{id}/messages/stream` and `conversationStore.loadMessages(id)`.
- Produces: `streamConversationMessage(conversationId,content,options)`, typed `SseEvent`, and `useChatStore()` with `send()`, `cancel()`, `retry()`, `draftAssistant`, `phase`, `citations`, and `error`.

- [ ] **Step 1: Write failing SSE framing tests**

Feed a `ReadableStream` whose chunks split UTF-8 characters and split `event:`/`data:` boundaries. Assert the parser emits:

```ts
[
  { event: 'message_start', data: { conversation_id: 'c1' } },
  { event: 'token', data: { text: '你好' } },
  { event: 'message_end', data: { content: '你好' } },
]
```

Also test `error` events, CRLF frames, final buffered frames, abort, and non-2xx JSON errors.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend; npm run test:run -- src/api/sse.spec.ts src/stores/chat.spec.ts`

Expected: FAIL because SSE parser and store do not exist.

- [ ] **Step 3: Implement fetch-based POST SSE parser**

Use `TextDecoder.decode(chunk, { stream: true })`; normalize CRLF; split frames on blank lines; join multiple `data:` lines with newline; parse data as JSON; expose `AbortSignal`; throw `ApiError` for HTTP failure. Do not use `EventSource`, because the endpoint requires POST with JSON.

- [ ] **Step 4: Implement the chat event reducer**

Map events as follows: `message_start` → streaming; `agent_status` → status label; `retrieval_start/result` → retrieval phase; `token` → append text with server token spacing preserved by inserting a single space between nonempty whitespace-split tokens; `citation` → deduplicate by source label and chunk ID; `message_end` → completed and reload persisted messages; `error` → failed while preserving draft content. Store the last submitted content for explicit retry only.

- [ ] **Step 5: Verify parser and state**

Run: `cd frontend; npm run test:run -- src/api/sse.spec.ts src/stores/chat.spec.ts; npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/api/sse.ts frontend/src/api/sse.spec.ts frontend/src/stores/chat.ts frontend/src/stores/chat.spec.ts
git commit -m "feat(frontend): add streaming chat client"
```

### Task 7: Chat-first interface and citation inspection

**Files:**
- Create: `frontend/src/layouts/ChatLayout.vue`
- Create: `frontend/src/components/chat/ChatHeader.vue`
- Create: `frontend/src/components/chat/MessageList.vue`
- Create: `frontend/src/components/chat/MessageBubble.vue`
- Create: `frontend/src/components/chat/AgentStatus.vue`
- Create: `frontend/src/components/chat/ChatComposer.vue`
- Create: `frontend/src/components/chat/CitationDrawer.vue`
- Create: `frontend/src/components/chat/MessageBubble.spec.ts`
- Create: `frontend/src/components/chat/ChatComposer.spec.ts`
- Modify: `frontend/src/pages/ChatPage.vue`
- Modify: `frontend/src/styles/layout.css`

**Interfaces:**
- Consumes: all four Pinia stores and `Message`/`MessageCitation` DTOs.
- Produces: complete chat route with conversation rail, knowledge-base picker, stream state, explicit retry, and citation drawer.

- [ ] **Step 1: Write failing component tests**

Assert that citation text `[S1]` renders as an accessible button, clicking it emits the matching citation, Enter submits, Shift+Enter inserts a line break, empty messages cannot submit, and the composer is disabled while a stream is active.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend; npm run test:run -- src/components/chat`

Expected: FAIL because chat components do not exist.

- [ ] **Step 3: Implement chat components**

Render user and assistant roles distinctly. Sanitize and render assistant content as text with citation labels converted to buttons; do not use unsanitized `v-html`. Show compact agent/retrieval status above the draft answer. Citation drawer displays filename from `citation.metadata.filename` when persisted, otherwise “未知文件”, plus section, page, score, quote, document ID, and chunk ID.

- [ ] **Step 4: Compose the responsive chat route**

Desktop: global sidebar, conversation rail, chat. Citation detail overlays from the right without permanently reserving a third column. Medium width collapses conversation history; narrow width uses overlays and a bottom citation sheet. Keep the composer visible after long histories without using a viewport-fixed element that obscures messages.

- [ ] **Step 5: Verify chat UI**

Run: `cd frontend; npm run test:run; npm run typecheck; npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/layouts frontend/src/components/chat frontend/src/pages/ChatPage.vue frontend/src/styles/layout.css
git commit -m "feat(frontend): build chat-first Agent interface"
```

### Task 8: Status page and cross-application feedback

**Files:**
- Create: `frontend/src/components/common/ToastHost.vue`
- Create: `frontend/src/stores/notifications.ts`
- Create: `frontend/src/stores/notifications.spec.ts`
- Modify: `frontend/src/pages/StatusPage.vue`
- Modify: `frontend/src/App.vue`

**Interfaces:**
- Consumes: `healthApi.live()` and `ApiError`.
- Produces: `useNotificationStore()` and a status page that distinguishes measured, unavailable, and unimplemented checks.

- [ ] **Step 1: Write failing status and notification tests**

Test notification expiry with fake timers and verify the status page labels PostgreSQL, Redis, MinIO, and Milvus as `后端未提供检测接口`, never `正常`.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd frontend; npm run test:run -- src/stores/notifications.spec.ts src/pages/StatusPage.spec.ts`

Expected: FAIL until store, page spec, and implementation exist. Create `frontend/src/pages/StatusPage.spec.ts` with the stated assertions before implementing.

- [ ] **Step 3: Implement feedback and status UI**

Report frontend loaded status locally, API health from `/health/live`, proxy/network latency measured around the request, and four unavailable infrastructure checks with explicit explanation. Add retry and last-checked time.

- [ ] **Step 4: Verify application feedback**

Run: `cd frontend; npm run test:run; npm run typecheck; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/common/ToastHost.vue frontend/src/stores/notifications.ts frontend/src/stores/notifications.spec.ts frontend/src/pages/StatusPage.vue frontend/src/pages/StatusPage.spec.ts frontend/src/App.vue
git commit -m "feat(frontend): add system status and notifications"
```

### Task 9: Docker delivery and same-origin proxy

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/.dockerignore`
- Modify: `frontend/vite.config.ts`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: Compose service `api:8000`.
- Produces: `frontend` service on `127.0.0.1:${RAG_AGENT_FRONTEND_PORT:-5173}:80`, SPA fallback, and `/api/v1` streaming proxy.

- [ ] **Step 1: Write the delivery configuration**

Vite dev proxy target is configurable by `VITE_API_PROXY_TARGET` and defaults to `http://127.0.0.1:8000`. Nginx must use:

```nginx
location /api/v1/ {
    proxy_pass http://api:8000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
location / {
    try_files $uri $uri/ /index.html;
}
```

Use a Node build stage and unprivileged Nginx runtime where the selected image supports port 8080; otherwise bind container port 80 and document it. Add a frontend health check against `/`.

- [ ] **Step 2: Validate Compose before building**

Run: `docker compose config --quiet`

Expected: exit 0 and frontend depends on healthy API.

- [ ] **Step 3: Build and start frontend with existing services**

Run: `docker compose up -d --build frontend`

Expected: frontend and required backend services start; frontend becomes healthy.

- [ ] **Step 4: Verify proxy and SPA fallback**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:5173/api/v1/health/live
(Invoke-WebRequest http://127.0.0.1:5173/chat).StatusCode
```

Expected: health body `{ "status": "ok" }` and `/chat` returns 200.

- [ ] **Step 5: Commit**

```powershell
git add frontend/Dockerfile frontend/nginx.conf frontend/.dockerignore frontend/vite.config.ts docker-compose.yml .env.example README.md
git commit -m "feat(frontend): add Docker Compose delivery"
```

### Task 10: End-to-end workflow and final verification

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/rag-workflow.spec.ts`
- Create: `frontend/e2e/fixtures.ts`
- Modify: `frontend/package.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: public UI, same-origin API, and deterministic Playwright route fixtures.
- Produces: reproducible browser regression for the complete user journey and final usage documentation.

- [ ] **Step 1: Write deterministic browser fixtures**

Intercept `/api/v1/**` and provide contract-shaped responses for one knowledge base, accepted upload, task progression, conversation creation, message history, and a POST SSE response containing `message_start`, `agent_status`, two `token` events, one citation, and `message_end`. Keep a mutable in-test state so create/delete actions change subsequent list responses.

- [ ] **Step 2: Write the failing end-to-end journey**

```ts
test('creates a knowledge base, ingests a document, chats, and opens a citation', async ({ page }) => {
  await page.goto('/knowledge-bases')
  await page.getByRole('button', { name: '创建知识库' }).click()
  await page.getByLabel('名称').fill('产品资料库')
  await page.getByLabel('Embedding 模型').fill('text-embedding-3-small')
  await page.getByLabel('向量维度').fill('1536')
  await page.getByRole('button', { name: '确认创建' }).click()
  await expect(page.getByText('产品资料库')).toBeVisible()
  await page.getByRole('link', { name: '管理文档' }).click()
  await page.getByLabel('选择文件').setInputFiles({
    name: 'sample.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 保修政策\n产品保修期为两年'),
  })
  await page.getByRole('button', { name: '上传文档' }).click()
  await expect(page.getByText('处理完成')).toBeVisible()
  await page.getByRole('link', { name: '新对话' }).click()
  await page.getByRole('button', { name: '新建会话' }).click()
  await page.getByLabel('会话标题').fill('保修政策咨询')
  await page.getByRole('button', { name: '创建并开始对话' }).click()
  await page.getByLabel('发送消息').fill('产品保修多久？')
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.getByText('产品保修期为两年')).toBeVisible()
  await page.getByRole('button', { name: '查看引用 S1' }).click()
  await expect(page.getByRole('dialog', { name: '引用来源' })).toContainText('产品保修期为两年')
})
```

- [ ] **Step 3: Run E2E and verify failure before missing UI fixes**

Run: `cd frontend; npm run test:e2e`

Expected: the test initially identifies any missing accessible label or workflow connection; capture the exact first failure.

- [ ] **Step 4: Make only the UI/accessibility fixes required by the journey**

Add stable accessible names and connect any missing route/store transition. Do not add test-only production branches or arbitrary `data-testid` attributes when a role or label can identify the element.

- [ ] **Step 5: Run complete verification**

Run:

```powershell
cd frontend
npm run test:run
npm run typecheck
npm run build
npm run test:e2e
cd ..
docker compose config --quiet
Invoke-RestMethod http://127.0.0.1:5173/api/v1/health/live
```

Expected: all tests and builds pass, Compose validates, and health returns `status: ok`.

- [ ] **Step 6: Review visual behavior manually**

At 1440px verify chat rail, composer, citations, tables, dialogs, and upload progress. At 768px verify collapsible conversation history. At 390px verify navigation overlay, bottom citation sheet, readable forms, and no horizontal page overflow.

- [ ] **Step 7: Commit**

```powershell
git add frontend/e2e frontend/playwright.config.ts frontend/package.json README.md frontend/src
git commit -m "test(frontend): cover complete RAG workflow"
```

## Final Acceptance Checklist

- [ ] All Vitest, component, type-check, build, and Playwright commands pass from a clean install.
- [ ] Docker Compose starts the frontend at port 5173 and proxies streaming requests without buffering.
- [ ] The real backend flow works with an existing configured model provider and a small UTF-8 Markdown file.
- [ ] No UI claims unsupported backend state.
- [ ] No secret or local `.env` value is committed.
- [ ] `git status --short` contains no unintended files.
