# Task 6 Report: POST SSE parser and streaming chat state

## Status

Implemented the Task 6 brief without modifying the Task 5 conversation store interface.

Created:

- `frontend/src/api/sse.ts`
- `frontend/src/api/sse.spec.ts`
- `frontend/src/stores/chat.ts`
- `frontend/src/stores/chat.spec.ts`

## TDD evidence

### SSE parser RED

Command:

```powershell
& 'C:\Users\DELL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'node_modules\vitest\vitest.mjs' run 'src/api/sse.spec.ts'
```

Observed expected failure before production implementation:

```text
Test Files  1 failed (1)
Tests       no tests
Error: Failed to resolve import "./sse" from "src/api/sse.spec.ts". Does the file exist?
```

### SSE parser GREEN

Same command after minimal implementation:

```text
Test Files  1 passed (1)
Tests       6 passed (6)
Exit code: 0
```

Coverage includes POST request contract, encoded conversation IDs, incremental UTF-8 decoding, split CRLF/frame boundaries, comments, unknown fields/events, multiple data lines, blank data, final unclosed frames, malformed payload filtering, normalized structured/generic `ApiError`, and AbortError propagation.

### Chat store RED

Command:

```powershell
& 'C:\Users\DELL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'node_modules\vitest\vitest.mjs' run 'src/stores/chat.spec.ts'
```

Observed expected failure before production implementation:

```text
Test Files  1 failed (1)
Tests       no tests
Error: Failed to resolve import "./chat" from "src/stores/chat.spec.ts". Does the file exist?
```

### Chat store GREEN

Same command after minimal implementation:

```text
Test Files  1 passed (1)
Tests       7 passed (7)
Exit code: 0
```

Coverage includes blank input, overlap prevention, optimistic user state without persisted-message duplication, all event transitions, readable token spacing, citation deduplication, authoritative completion/refresh, backend failure with partial preservation, cancellation without automatic retry, explicit retry, stale generation guards, wrong-conversation refresh prevention, and refresh failure handling.

## Full verification

All commands were run from `frontend` using the Codex-bundled Node executable because `node` is not present on the shell PATH.

### Full tests

```powershell
& 'C:\Users\DELL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'node_modules\vitest\vitest.mjs' run
```

```text
Test Files  9 passed (9)
Tests       71 passed (71)
Exit code: 0
```

### Typecheck

```powershell
& 'C:\Users\DELL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'node_modules\vue-tsc\bin\vue-tsc.js' --noEmit -p tsconfig.json
```

```text
Exit code: 0
No diagnostics.
```

### Production build

```powershell
& 'C:\Users\DELL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'node_modules\vite\bin\vite.js' build
```

```text
vite v7.3.6 building client environment for production...
92 modules transformed.
✓ built in 2.02s
Exit code: 0
```

### Diff hygiene

```text
git diff --check
Exit code: 0
```

## Self-review

- Confirmed the parser uses only `fetch` POST and never `EventSource` or automatic retry.
- Confirmed incremental `TextDecoder` flushing and line parsing handle byte, field, and frame splits without corrupting multibyte characters.
- Confirmed runtime validation prevents malformed/unknown events from reaching the store reducer.
- Confirmed intentional cancellation is distinguished from backend failure and preserves accumulated output.
- Confirmed generation checks run before every event reduction and are also passed into persisted-message refresh.
- Confirmed optimistic state is separate from `messagesByConversation`, then cleared only after a current, successful persisted refresh.
- Confirmed only Task 6 files and this report will be staged; pre-existing untracked task artifacts remain untouched.

## Commit

Commit message: `feat(frontend): add streaming chat client`

The resulting hash is recorded in the task handoff because embedding a commit's own hash in its contents is circular.

## Concerns

- No known product-code concerns.
- Local environment note: `node` is absent from PATH, so verification used the bundled Node executable directly; this does not affect the project output.

## Fix round 1: premature clean EOF

### Scope and root cause

Addressed only the Important open finding from `task-6-review.md`. The store previously handled thrown transport failures and explicit terminal events, but did not check whether a current async iterable exhausted naturally without `message_end` or `error`. That path cleared the controller while leaving `phase` nonterminal and retry disabled.

The deferred Minor finding about explicit reader cancellation/release was intentionally not changed in this fix round.

### RED

Command:

```powershell
& 'C:\Users\DELL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'node_modules\vitest\vitest.mjs' run 'src/stores/chat.spec.ts'
```

Observed before the fix:

```text
Test Files  1 failed (1)
Tests       2 failed | 7 passed (9)
null-body case: expected 'failed', received 'sending'
partial clean-EOF case: expected 'failed', received 'streaming'
Exit code: 1
```

### GREEN

The store now tracks whether its current generation observed a terminal event. Natural exhaustion without one transitions only the current generation to `failed`, reports `连接提前结束，请重试。`, preserves the draft, and enables explicit retry. Cancelled and stale generations remain protected by the existing generation guard.

Focused command after the fix:

```text
Test Files  1 passed (1)
Tests       9 passed (9)
Exit code: 0
```

Regression coverage includes a real 2xx `Response` with a null body, `message_start` plus partial token followed by clean EOF, successful explicit retry for both, cancelled clean EOF, and a stale older generation.

### Fresh full verification

Full tests:

```text
Test Files  9 passed (9)
Tests       73 passed (73)
Exit code: 0
```

Typecheck:

```text
vue-tsc --noEmit -p tsconfig.json
Exit code: 0
No diagnostics.
```

Production build:

```text
vite v7.3.6
92 modules transformed.
✓ built in 1.90s
Exit code: 0
```

### Fix commit

Planned message: `fix(frontend): fail premature chat stream EOF`

The resulting hash is recorded in the task handoff.
