# Task 5 report: Conversation management and persisted messages

## Status

Complete. Conversation lists are cached per knowledge base, persisted messages are stably ordered, and conversation create/delete/select flows are connected to the conversation and chat pages.

## Files

- `frontend/src/stores/conversations.ts`
- `frontend/src/stores/conversations.spec.ts`
- `frontend/src/components/conversations/ConversationList.vue`
- `frontend/src/components/conversations/ConversationCreateDialog.vue`
- `frontend/src/pages/ConversationsPage.vue`
- `frontend/src/pages/ChatPage.vue`

## Red / green evidence

- RED: `pnpm test:run -- src/stores/conversations.spec.ts` failed before the store and components existed, with `Failed to resolve import "./conversations"`.
- RED: invalid `?conversation=not-a-uuid` test failed because the page requested the API once.
- GREEN: the final suite reports 7 passing files and 54 passing tests.

## Verification

From `frontend/`, with the bundled Node runtime temporarily added to `PATH`:

- `pnpm test:run` — pass, 54 tests.
- `pnpm typecheck` — pass.
- `pnpm build` — pass.
- `git diff --check` — pass.

## Commit

`feat(frontend): add conversation management`

## Self-review

- Lists are keyed and cached by knowledge-base ID, so switching knowledge bases cannot display another KB's conversations.
- Equal message timestamps preserve the received server ordering.
- Create trims and validates titles, updates only the target cache, selects the new conversation, and page flows navigate to its query route.
- Deletion clears all cached locations, messages, and active selection for the conversation.
- Message counts use own-key presence, so zero is displayed only for a loaded empty message array.
- There is no rename control or rename API use.
- Chat handles `?conversation=<uuid>` and `?new=1`; invalid or stale IDs provide a recovery link.

## Concerns

- The runtime exposes `pnpm`, but does not put `node` on `PATH`; verification commands require a temporary PATH prefix for the bundled Node directory. No project configuration was changed.

## Fix round 1/5

### Status

Complete. All findings from `task-5-review.md` are addressed.

### Files changed

- `frontend/src/stores/conversations.ts`
- `frontend/src/components/conversations/ConversationCreateDialog.vue`
- `frontend/src/pages/ChatPage.vue`
- `frontend/src/stores/conversations.spec.ts`

### Red / green

- RED: the added tests failed because 200-character titles were rejected and delayed earlier route resolutions selected the wrong conversation (`4 failed, 54 passed`).
- GREEN: after the minimal fixes, the full suite reports `7 passed` files and `58 passed` tests.

### Fixes

- Store and dialog now allow titles from 1 through 200 characters and reject 201 characters; the input has `maxlength="200"`.
- Chat route resolution uses a monotonic generation token. Every post-await update is active-route-only, and `loadMessages` accepts the same guard so stale responses and errors cannot update shared conversation state.
- Tests cover delayed conversation-to-conversation and conversation-to-new transitions, plus the `?new=1` creation flow replacing the route with `?conversation=<uuid>`.

### Commands and output

- `pnpm test:run -- src/stores/conversations.spec.ts` — pass, 7 files / 58 tests.
- `pnpm test:run` — pass, 7 files / 58 tests.
- `pnpm typecheck` — pass.
- `pnpm build` — pass.

### Commit

`fix(frontend): guard conversation route resolution`

### Concerns

- Verification continues to require the temporary bundled-Node PATH prefix noted above. No source or project configuration concern remains.
