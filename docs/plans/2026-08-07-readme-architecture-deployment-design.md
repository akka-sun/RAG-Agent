# README Architecture and Deployment Design

## Goal

Replace the current README with a concise architecture and deployment manual for the
completed Stage 3 system.

## Audience

Developers who need to understand the service boundaries, start the complete stack,
apply database migrations, verify health, find the API documentation, and run quality
checks.

## Structure

1. Project purpose and implemented capabilities.
2. Mermaid architecture diagram covering FastAPI, ARQ Worker, PostgreSQL, Redis, and MinIO.
3. Asynchronous ingestion data flow from multipart upload through indexing and status polling.
4. Runtime requirements and environment configuration.
5. Docker Compose deployment commands: configure, build/start, migrate, inspect health, view
   logs, and stop.
6. API documentation URL and a compact endpoint inventory.
7. Formatting, linting, type-checking, unit, integration, and end-to-end verification commands.
8. Current scope and limitations.

## Constraints

- Remove the existing README body rather than incrementally appending to it.
- Keep commands PowerShell-compatible because the repository is currently developed on Windows.
- Describe only behavior verified by the Stage 3 implementation and tests.
- Do not include the previous step-by-step upload walkthrough.
- Keep secrets in `.env`; show only repository-safe example commands.
- Preserve UTF-8 Chinese documentation.

## Acceptance Criteria

- A new developer can identify every long-running service and its storage responsibility.
- The documented deployment reaches healthy API, PostgreSQL, Redis, MinIO, and Worker services.
- Migration, log inspection, shutdown, and all verification commands are present.
- API routes and current limitations match the implemented code.
