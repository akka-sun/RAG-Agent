from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from minio import Minio
from minio.error import S3Error
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db import async_session_factory
from app.infrastructure.object_storage import MinioObjectStorage
from app.infrastructure.redis_index import RedisDocumentIndex
from app.services.ingestion import IngestionService

pytestmark = pytest.mark.e2e

API_URL = os.getenv("E2E_API_URL", "http://api:8000/api/v1")
POLL_TIMEOUT_SECONDS = 30.0


def _compose_logs() -> str:
    if shutil.which("docker") is None:
        return "Docker CLI is unavailable; run `docker compose logs api worker --tail 100`."
    project = os.getenv("COMPOSE_PROJECT_NAME")
    command = ["docker", "compose"]
    if project:
        command.extend(["--project-name", project])
    command.extend(["logs", "api", "worker", "--tail", "100", "--no-color"])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Unable to collect Compose logs: {exc}"
    return (result.stdout + result.stderr).strip()


async def _wait_for_completed(client: httpx.AsyncClient, task_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    last_payload: object = None
    while time.monotonic() < deadline:
        response = await client.get(f"/ingestion-tasks/{task_id}")
        response.raise_for_status()
        last_payload = cast(dict[str, Any], response.json())
        status = last_payload["status"]
        if status == "completed":
            return last_payload
        if status == "failed":
            pytest.fail(f"Ingestion failed: {last_payload}\n\n{_compose_logs()}")
        await asyncio.sleep(0.2)
    pytest.fail(
        f"Ingestion did not complete within {POLL_TIMEOUT_SECONDS}s; "
        f"last task response: {last_payload}\n\n{_compose_logs()}"
    )


@pytest.mark.asyncio
async def test_async_ingestion_is_idempotent_and_delete_cleans_all_stores() -> None:
    settings = get_settings()
    redis = cast(Any, Redis).from_url(settings.redis_url)
    minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    storage = MinioObjectStorage(minio, settings.minio_bucket)
    index = RedisDocumentIndex(redis)

    async with httpx.AsyncClient(base_url=API_URL, timeout=10) as client:
        kb_response = await client.post(
            "/knowledge-bases",
            json={
                "name": f"e2e-async-ingestion-{time.time_ns()}",
                "description": "Task 11 real Compose acceptance",
                "embedding_model": "hashing",
                "embedding_dimension": 256,
            },
        )
        assert kb_response.status_code == 201, kb_response.text
        knowledge_base_id = kb_response.json()["id"]

        upload_response = await client.post(
            f"/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    "acceptance.md",
                    b"# Acceptance\n\nReal async ingestion.\n",
                    "text/markdown",
                )
            },
        )
        assert upload_response.status_code == 202, upload_response.text
        accepted = upload_response.json()
        assert accepted["status"] == "pending"
        document_id = accepted["document_id"]
        task_id = accepted["task_id"]

        task = await _wait_for_completed(client, task_id)
        assert task["progress"] == 100
        assert task["stage"] == "completed"

        document_response = await client.get(
            f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
        )
        document_response.raise_for_status()
        document = document_response.json()
        assert document["status"] == "completed"
        assert document["chunk_count"] > 0

        source_response = await client.get(
            f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/source"
        )
        assert source_response.status_code == 200
        assert source_response.content == b"# Acceptance\n\nReal async ingestion.\n"
        parsed_response = await client.get(
            f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/parsed"
        )
        assert parsed_response.status_code == 200
        assert parsed_response.json()["text"] == "# Acceptance\n\nReal async ingestion.\n"

        kb_uuid, document_uuid = UUID(knowledge_base_id), UUID(document_id)
        chunks = await index.get_document(kb_uuid, document_uuid)
        assert len(chunks) == document["chunk_count"]

        service = IngestionService(async_session_factory, storage, index)
        await service.run(task_id, document_id)
        chunks_after_reentry = await index.get_document(kb_uuid, document_uuid)
        assert len(chunks_after_reentry) == len(chunks)
        assert [chunk.chunk_id for chunk in chunks_after_reentry] == [
            chunk.chunk_id for chunk in chunks
        ]

        delete_response = await client.delete(
            f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
        )
        assert delete_response.status_code == 204, delete_response.text
        assert (
            await client.get(f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}")
        ).status_code == 404

    async with async_session_factory() as session:
        remaining = await session.execute(
            text("SELECT count(*) FROM documents WHERE id = :id"), {"id": document_id}
        )
        assert remaining.scalar_one() == 0
    assert await index.get_document(kb_uuid, document_uuid) == []
    for object_key in (document["source_object_key"], document["parsed_object_key"]):
        with pytest.raises(S3Error) as exc_info:
            await storage.get(object_key)
        assert exc_info.value.code in {"NoSuchKey", "NoSuchObject"}
    redis.close()
