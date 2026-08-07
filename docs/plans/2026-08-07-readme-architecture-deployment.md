# README Architecture and Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the README with an accurate architecture and Docker Compose deployment manual, then merge the verified Stage 3 branch into `main`.

**Architecture:** Documentation is derived from the committed Compose services, API routes, migrations, and verification commands. The feature branch is verified before merge, then `main` is fast-forwarded or merged and verified again before push.

**Tech Stack:** Markdown, Mermaid, PowerShell, Docker Compose, FastAPI, ARQ, PostgreSQL, Redis, MinIO, Git.

---

### Task 1: Rewrite README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the existing README body**

Write sections for project scope, implemented capabilities, a Mermaid service diagram, ingestion flow, requirements, `.env` setup, deployment, migrations, health checks, logs, shutdown, API inventory, verification, and current limitations.

- [ ] **Step 2: Cross-check documented commands**

Run:

```powershell
docker compose config --quiet
docker compose ps
```

Expected: valid Compose configuration and all long-running services listed.

- [ ] **Step 3: Cross-check routes and migrations**

Compare the endpoint inventory with `app/main.py`, `app/api/routes/`, and the three Alembic revisions. Remove any undocumented or nonexistent behavior.

- [ ] **Step 4: Verify Markdown and repository checks**

Run:

```powershell
docker compose exec api uv run --no-sync ruff format --check app tests
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
git diff --check
```

Expected: all commands exit with code 0.

- [ ] **Step 5: Commit**

```powershell
git add README.md docs/plans/2026-08-07-readme-architecture-deployment.md
git commit -m "docs: 重写项目架构与部署说明"
```

### Task 2: Merge and Publish Main

**Files:**
- Verify: repository history and tracked worktree state

- [ ] **Step 1: Verify the feature branch**

Run unit, integration, and end-to-end suites in the healthy Compose stack. Expected: all tests pass.

- [ ] **Step 2: Push the feature branch**

```powershell
git push origin codex/stage-3-async-ingestion
```

- [ ] **Step 3: Merge into main**

From the primary worktree, update `main`, merge `codex/stage-3-async-ingestion`, and confirm no unrelated files are included.

- [ ] **Step 4: Verify the merged result**

Run the same formatting, lint, type, unit, integration, and end-to-end commands against merged `main`. Expected: all exit with code 0.

- [ ] **Step 5: Push main**

```powershell
git push origin main
```

Expected: local `main` and `origin/main` resolve to the same commit.
