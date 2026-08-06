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
- Task 9: Idempotent ingestion worker state machine with observable progress.
- Task 10: Document query, download, retry, and coordinated deletion APIs.

Validation for Task 7: PostgreSQL main/test migrations, 102 unit and integration tests,
Ruff, and Pyright passed. One existing Starlette deprecation warning remains.

Validation for Task 8: Redis index unit tests, overwrite/isolation/delete behavior,
Ruff, and code review passed.

Validation for Task 9: 11 targeted state-machine and worker lifecycle tests, Ruff,
and code review passed.

Validation for Task 10: 125 unit and integration tests, real PostgreSQL retry/delete
coverage, Ruff, targeted Pyright, and code review passed.

Pending:

- Task 11: End-to-end acceptance and learning documentation.
