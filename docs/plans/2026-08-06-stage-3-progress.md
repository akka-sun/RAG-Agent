# Stage 3 Progress

As of 2026-08-06, the asynchronous ingestion implementation is complete through
Task 7. The completed work is on branch `codex/stage-3-async-ingestion`.

Completed:

- Task 1: Redis, MinIO, ARQ worker infrastructure and reproducible container dependencies.
- Task 2: Document and ingestion task models, constraints, relationships, and migration.
- Task 3: Upload schemas, error contracts, state transitions, and HTTP error handling.
- Task 4: PostgreSQL document and ingestion task repositories with atomic claiming.
- Task 5: MinIO object storage adapter with cancellation-safe response cleanup.
- Task 6: ARQ queue adapter with fixed job IDs and connection failure mapping.
- Task 7: Multipart upload API and cross-storage compensation behavior.
- Task 8: Redis shared document index with atomic document-level replacement.

Validation for Task 7: PostgreSQL main/test migrations, 102 unit and integration tests,
Ruff, and Pyright passed. One existing Starlette deprecation warning remains.

Validation for Task 8: Redis index unit tests, overwrite/isolation/delete behavior,
Ruff, and code review passed.

Pending:

- Task 9: Ingestion worker state machine.
- Task 10: Query, download, retry, and delete APIs.
- Task 11: End-to-end acceptance and learning documentation.
