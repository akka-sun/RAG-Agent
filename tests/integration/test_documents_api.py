import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies import get_document_service
from app.core.exceptions import DocumentStorageUnavailableError, UnsupportedDocumentError
from app.models.document import Document
from app.models.ingestion_task import IngestionTask
from app.schemas.documents import MAX_DOCUMENT_SIZE


async def test_upload_document_accepts_multipart_and_returns_202(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    document_id = uuid.uuid4()
    task_id = uuid.uuid4()
    service = AsyncMock()
    service.upload.return_value = (
        Document(id=document_id, knowledge_base_id=uuid.uuid4()),
        IngestionTask(id=task_id, document_id=document_id),
    )
    app.dependency_overrides[get_document_service] = lambda: service
    knowledge_base_id = uuid.uuid4()

    response = await client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("notes.md", b"# notes", "text/markdown")},
    )

    assert response.status_code == 202
    assert response.json() == {
        "document_id": str(document_id),
        "task_id": str(task_id),
        "status": "pending",
    }
    service.upload.assert_awaited_once_with(
        knowledge_base_id, "notes.md", "text/markdown", b"# notes"
    )


async def test_upload_reads_at_most_validation_limit_plus_one(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    service = AsyncMock()
    service.upload.side_effect = UnsupportedDocumentError("too large")
    app.dependency_overrides[get_document_service] = lambda: service

    response = await client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/documents",
        files={"file": ("large.md", b"x" * (MAX_DOCUMENT_SIZE + 2), "text/markdown")},
    )

    assert response.status_code == 422
    assert len(service.upload.await_args.args[3]) == MAX_DOCUMENT_SIZE + 1
    assert response.json()["error"]["code"] == "unsupported_document"


async def test_storage_failure_uses_unified_error_response(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    service = AsyncMock()
    service.upload.side_effect = DocumentStorageUnavailableError("storage unavailable")
    app.dependency_overrides[get_document_service] = lambda: service

    response = await client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/documents",
        files={"file": ("notes.md", b"notes", "text/markdown")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "document_storage_unavailable"
