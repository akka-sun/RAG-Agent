# 阶段 6：会话、SSE 与引用实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加持久化会话、消息、引用和 SSE 流式对话接口，使 Agent 回答能恢复、审计并精确追溯引用来源。

**Architecture:** PostgreSQL 保存 `conversations`、`messages`、`message_citations`；`ConversationService` 管理会话和消息事务；`SSEChatService` 包装阶段 5 Agent 运行并产生规范事件；最终 assistant message 与 citations 在同一个事务提交。

**Tech Stack:** FastAPI SSE `StreamingResponse`, SQLAlchemy async, PostgreSQL, LangGraph Agent service, pytest, HTTPX streaming tests, Ruff, Pyright.

## Global Constraints

- Final assistant messages and citations commit in one PostgreSQL transaction.
- Citations must refer to evidence returned in the same agent run.
- A hallucinated or stale citation is a validation error and must not be persisted.
- SSE events are limited to `message_start`, `agent_status`, `retrieval_start`, `retrieval_result`, `token`, `citation`, `message_end`, and `error`.
- Runtime code must never hard-code credentials.
- Every `Fake*` type shown in test snippets is a test-local class defined in the same test file immediately above the test, implementing only the attributes and methods asserted by that test.

---

## File Structure

- Create `app/models/conversation.py`
- Create `app/models/message.py`
- Create `app/models/message_citation.py`
- Modify `app/models/__init__.py`
- Create Alembic migration for conversations, messages, citations.
- Create `app/repositories/conversations.py`
- Create `app/repositories/messages.py`
- Create `app/schemas/conversations.py`
- Create `app/schemas/chat.py`
- Create `app/services/conversations.py`
- Create `app/services/sse_chat.py`
- Create `app/api/routes/conversations.py`
- Create `app/api/routes/chat.py`
- Modify `app/api/routes/__init__.py`
- Modify `app/api/dependencies.py`
- Add unit, integration, and streaming API tests.
- Update `README.md` and `docs/learning-roadmap.md`.

---

### Task 1: Conversation Data Model and Migration

**Files:**
- Create: `app/models/conversation.py`
- Create: `app/models/message.py`
- Create: `app/models/message_citation.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/20260809_0004_add_conversations_messages_citations.py`
- Test: `tests/unit/test_conversation_models.py`
- Test: `tests/integration/test_migrations.py`

**Interfaces:**
- Produces ORM models `Conversation`, `Message`, `MessageCitation`.
- Consumes `KnowledgeBase` and `Document` models.

- [ ] **Step 1: Write failing model test**

```python
def test_message_citation_requires_existing_message_and_document():
    citation_columns = inspect(MessageCitation).columns

    assert "message_id" in citation_columns
    assert "document_id" in citation_columns
    assert "chunk_id" in citation_columns
    assert "source_label" in citation_columns
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_conversation_models.py -v`

Expected: FAIL because models do not exist.

- [ ] **Step 3: Implement models and migration**

Conversation fields: `id`, `knowledge_base_id`, `title`, `created_at`, `updated_at`.

Message fields: `id`, `conversation_id`, `role`, `content`, `status`, `created_at`, `token_count`.

Citation fields: `id`, `message_id`, `document_id`, `chunk_id`, `source_label`, `quote`, `page_number`, `section`, `score`, `metadata`.

- [ ] **Step 4: Verify migration**

Run:

```powershell
uv run --no-sync pytest tests/unit/test_conversation_models.py -v
uv run --no-sync pytest tests/integration/test_migrations.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/models/conversation.py app/models/message.py app/models/message_citation.py app/models/__init__.py alembic/versions/20260809_0004_add_conversations_messages_citations.py tests/unit/test_conversation_models.py tests/integration/test_migrations.py
git commit -m "feat: 增加会话消息与引用数据模型"
```

---

### Task 2: Repositories

**Files:**
- Create: `app/repositories/conversations.py`
- Create: `app/repositories/messages.py`
- Test: `tests/integration/test_conversation_repositories.py`

**Interfaces:**
- Produces: `ConversationRepository.create`, `list_by_knowledge_base`, `get`, `delete`; `MessageRepository.add_user_message`, `add_assistant_message_with_citations`, `list_by_conversation`.
- Consumes ORM models from Task 1.

- [ ] **Step 1: Write failing repository test**

```python
async def test_add_assistant_message_rolls_back_invalid_citation(db_session):
    repo = MessageRepository(db_session)
    conversation = await create_conversation(db_session)

    with pytest.raises(CitationValidationError):
        await repo.add_assistant_message_with_citations(
            conversation_id=conversation.id,
            content="answer [S1]",
            citations=[
                MessageCitationInput(source_label="S2", document_id=uuid.uuid4(), chunk_id="c1")
            ],
            valid_labels={"S1"},
        )

    assert await repo.list_by_conversation(conversation.id) == []
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/integration/test_conversation_repositories.py -v`

Expected: FAIL because repositories do not exist.

- [ ] **Step 3: Implement repositories**

`add_assistant_message_with_citations` must validate labels before flush. It must add message and citations within the caller's current transaction.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/integration/test_conversation_repositories.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/repositories/conversations.py app/repositories/messages.py tests/integration/test_conversation_repositories.py
git commit -m "feat: 增加会话与消息 Repository"
```

---

### Task 3: Conversation Schemas and Service

**Files:**
- Create: `app/schemas/conversations.py`
- Create: `app/services/conversations.py`
- Test: `tests/unit/test_conversation_schemas.py`
- Test: `tests/unit/test_conversation_service.py`

**Interfaces:**
- Produces: `ConversationCreate`, `ConversationResponse`, `MessageResponse`, `ConversationService`.
- Consumes repositories from Task 2.

- [ ] **Step 1: Write failing schema/service tests**

```python
def test_conversation_title_trims_whitespace():
    payload = ConversationCreate(title="  Support Docs  ")

    assert payload.title == "Support Docs"


async def test_create_conversation_requires_existing_knowledge_base():
    service = ConversationService(
        knowledge_bases=MissingKnowledgeBaseRepo(), conversations=FakeConversationRepo()
    )

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.create(knowledge_base_id=uuid.uuid4(), title="Chat")
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --no-sync pytest tests/unit/test_conversation_schemas.py tests/unit/test_conversation_service.py -v`

Expected: FAIL because schema and service are missing.

- [ ] **Step 3: Implement schemas and service**

Validate non-empty title, route knowledge base existence through existing repository, and map ORM objects into response schemas.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_conversation_schemas.py tests/unit/test_conversation_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/schemas/conversations.py app/services/conversations.py tests/unit/test_conversation_schemas.py tests/unit/test_conversation_service.py
git commit -m "feat: 增加会话业务服务"
```

---

### Task 4: Conversation REST API

**Files:**
- Create: `app/api/routes/conversations.py`
- Modify: `app/api/routes/__init__.py`
- Modify: `app/api/dependencies.py`
- Test: `tests/integration/test_conversations_api.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/knowledge-bases/{knowledge_base_id}/conversations`
  - `GET /api/v1/knowledge-bases/{knowledge_base_id}/conversations`
  - `GET /api/v1/conversations/{conversation_id}`
  - `DELETE /api/v1/conversations/{conversation_id}`
  - `GET /api/v1/conversations/{conversation_id}/messages`
- Consumes `ConversationService`.

- [ ] **Step 1: Write failing API test**

```python
async def test_create_and_list_conversations(async_client):
    kb = await create_kb(async_client)

    created = await async_client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/conversations",
        json={"title": "Research"},
    )

    assert created.status_code == 201
    listed = await async_client.get(f"/api/v1/knowledge-bases/{kb['id']}/conversations")
    assert listed.json()[0]["title"] == "Research"
```

- [ ] **Step 2: Run failing API test**

Run: `uv run --no-sync pytest tests/integration/test_conversations_api.py -v`

Expected: FAIL because routes are missing.

- [ ] **Step 3: Implement API routes**

Use existing error handling conventions. Return `201` on create, `204` on delete, and `404` for missing conversation.

- [ ] **Step 4: Verify API tests**

Run: `uv run --no-sync pytest tests/integration/test_conversations_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/api/routes/conversations.py app/api/routes/__init__.py app/api/dependencies.py tests/integration/test_conversations_api.py
git commit -m "feat: 增加会话 REST API"
```

---

### Task 5: SSE Event Contracts

**Files:**
- Create: `app/schemas/chat.py`
- Create: `app/services/sse_chat.py`
- Test: `tests/unit/test_sse_chat.py`

**Interfaces:**
- Produces: `SSEEvent`, `format_sse(event: SSEEvent) -> str`, `SSEChatService.stream(conversation_id: UUID, user_message: str) -> AsyncIterator[SSEEvent]`.
- Consumes `AgentChatService` from Stage 5 and `MessageRepository`.

- [ ] **Step 1: Write failing formatter test**

```python
def test_format_sse_serializes_event_name_and_json_data():
    event = SSEEvent(event="token", data={"text": "hello"})

    assert format_sse(event) == 'event: token\ndata: {"text":"hello"}\n\n'
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_sse_chat.py -v`

Expected: FAIL because SSE module does not exist.

- [ ] **Step 3: Implement SSE schema and formatter**

Validate event names against the fixed allowed set. Use compact JSON with UTF-8 content.

- [ ] **Step 4: Implement stream service**

The stream emits `message_start`, status events, retrieval events, token events, citation events, and `message_end`. On exception it emits `error` and records failure state.

- [ ] **Step 5: Verify unit tests**

Run: `uv run --no-sync pytest tests/unit/test_sse_chat.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/schemas/chat.py app/services/sse_chat.py tests/unit/test_sse_chat.py
git commit -m "feat: 定义 SSE 对话事件流"
```

---

### Task 6: Streaming Chat API and Citation Persistence

**Files:**
- Create: `app/api/routes/chat.py`
- Modify: `app/api/routes/__init__.py`
- Modify: `app/api/dependencies.py`
- Test: `tests/integration/test_chat_sse_api.py`

**Interfaces:**
- Produces: `POST /api/v1/conversations/{conversation_id}/messages/stream`.
- Consumes `SSEChatService`.

- [ ] **Step 1: Write failing streaming API test**

```python
async def test_stream_chat_persists_assistant_message_and_citation(async_client):
    conversation = await create_conversation(async_client)

    async with async_client.stream(
        "POST",
        f"/api/v1/conversations/{conversation['id']}/messages/stream",
        json={"content": "Explain retention policy"},
    ) as response:
        body = await response.aread()

    assert response.status_code == 200
    assert b"event: message_end" in body
    messages = await async_client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.json()[-1]["role"] == "assistant"
    assert messages.json()[-1]["citations"][0]["source_label"] == "S1"
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/integration/test_chat_sse_api.py -v`

Expected: FAIL because streaming route is missing.

- [ ] **Step 3: Implement route**

Return `StreamingResponse` with `text/event-stream`. The route must load the conversation, save the user message, run the stream, then commit final assistant message and citations atomically.

- [ ] **Step 4: Verify streaming API**

Run: `uv run --no-sync pytest tests/integration/test_chat_sse_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/api/routes/chat.py app/api/routes/__init__.py app/api/dependencies.py tests/integration/test_chat_sse_api.py
git commit -m "feat: 增加 SSE 对话 API 与引用落库"
```

---

### Task 7: Stage 6 Documentation and Acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`
- Create: `docs/plans/2026-08-09-stage-6-progress.md`

**Interfaces:**
- Consumes: Tasks 1-6 verification outputs.
- Produces: documented conversation and SSE workflow.

- [ ] **Step 1: Update README**

Document conversation APIs, SSE event schema, persistence guarantees, and citation validation.

- [ ] **Step 2: Update roadmap**

Add Stage 6 completion record and oral review prompts about stream lifecycle and citation transactions.

- [ ] **Step 3: Run final gates**

Run:

```powershell
docker compose exec api uv run --no-sync alembic upgrade head
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/learning-roadmap.md docs/plans/2026-08-09-stage-6-progress.md
git commit -m "docs: 完成阶段六会话与 SSE 验收记录"
```
