import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies import get_document_service
from app.core.exceptions import (
    DocumentCleanupFailedError,
    DocumentStorageUnavailableError,
    InvalidStatusTransitionError,
    UnsupportedDocumentError,
)
from app.models.document import Document
from app.models.ingestion_task import IngestionTask
from app.schemas.documents import MAX_DOCUMENT_SIZE
from app.services.documents import DocumentService


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
        knowledge_base_id,
        "notes.md",
        "text/markdown",
        b"# notes",
        parser_name=None,
    )


async def test_upload_document_passes_pdf_parser_selection(
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
        data={"parser": "paddlex"},
        files={"file": ("scan.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 202
    service.upload.assert_awaited_once_with(
        knowledge_base_id,
        "scan.pdf",
        "application/pdf",
        b"%PDF",
        parser_name="paddlex",
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


async def test_document_management_routes_delegate_to_service(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()
    task_id = uuid.uuid4()
    document = Document(
        id=document_id,
        knowledge_base_id=knowledge_base_id,
        filename="notes.md",
        content_type="text/markdown",
        size_bytes=7,
        parser_name="local",
        source_object_key="source",
        status="completed",
        chunk_count=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    task = IngestionTask(
        id=task_id,
        document_id=document_id,
        status="completed",
        stage="completed",
        progress=100,
        created_at=datetime.now(UTC),
    )
    service = AsyncMock()
    service.list_documents.return_value = [document]
    service.get_document.return_value = document
    service.get_task.return_value = task
    service.download_source.return_value = ("notes.md", "text/markdown", b"# notes")
    service.download_parsed.return_value = b'{"text":"notes"}'
    service.download_image.return_value = ("image/png", b"png-data")
    service.retry.return_value = IngestionTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status="pending",
        stage="queued",
        progress=0,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_document_service] = lambda: service

    listed = await client.get(f"/api/v1/knowledge-bases/{knowledge_base_id}/documents")
    detailed = await client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
    )
    polled = await client.get(f"/api/v1/ingestion-tasks/{task_id}")
    source = await client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/source"
    )
    parsed = await client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/parsed"
    )
    image = await client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/images/0"
    )
    retried = await client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/retry"
    )
    deleted = await client.delete(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
    )

    assert listed.status_code == detailed.status_code == polled.status_code == 200
    assert source.content == b"# notes"
    assert source.headers["content-type"].startswith("text/markdown")
    assert "notes.md" in source.headers["content-disposition"]
    assert parsed.content == b'{"text":"notes"}'
    assert image.content == b"png-data"
    assert image.headers["content-type"].startswith("image/png")
    service.download_image.assert_awaited_once_with(knowledge_base_id, document_id, 0)
    assert retried.status_code == 202
    assert retried.json()["status"] == "pending"
    assert deleted.status_code == 204
    service.delete.assert_awaited_once_with(knowledge_base_id, document_id)


async def test_retry_rejects_non_failed_document() -> None:
    knowledge_base_id = uuid.uuid4()
    document = Document(id=uuid.uuid4(), knowledge_base_id=knowledge_base_id, status="completed")
    documents = AsyncMock()
    documents.get_for_update.return_value = document
    service = DocumentService(
        AsyncMock(), documents, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    )

    with pytest.raises(InvalidStatusTransitionError):
        await service.retry(knowledge_base_id, document.id)


async def test_delete_cleans_external_resources_before_database() -> None:
    knowledge_base_id = uuid.uuid4()
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        source_object_key="source",
        parsed_object_key="parsed",
    )
    documents = AsyncMock()
    documents.get_for_update.return_value = document
    tasks = AsyncMock()
    tasks.has_active_task.return_value = False
    session = AsyncMock()
    storage = AsyncMock()
    storage.get.return_value = b"{}"
    index = AsyncMock()
    service = DocumentService(AsyncMock(), documents, tasks, session, storage, AsyncMock(), index)

    await service.delete(knowledge_base_id, document.id)

    index.delete_document.assert_awaited_once_with(knowledge_base_id, document.id)
    assert [call.args[0] for call in storage.delete.await_args_list] == ["parsed", "source"]
    tasks.delete_by_document.assert_awaited_once_with(document.id)
    documents.delete.assert_awaited_once_with(document)
    session.commit.assert_awaited_once()


async def test_delete_removes_parser_assets_listed_in_parsed_document() -> None:
    knowledge_base_id = uuid.uuid4()
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        source_object_key="source",
        parsed_object_key="parsed",
    )
    documents = AsyncMock()
    documents.get_for_update.return_value = document
    tasks = AsyncMock()
    tasks.has_active_task.return_value = False
    storage = AsyncMock()
    storage.get.return_value = b'{"assets":[{"object_key":"images/0000.png"}]}'
    service = DocumentService(
        AsyncMock(), documents, tasks, AsyncMock(), storage, AsyncMock(), AsyncMock()
    )

    await service.delete(knowledge_base_id, document.id)

    assert [call.args[0] for call in storage.delete.await_args_list] == [
        "images/0000.png",
        "parsed",
        "source",
    ]


async def test_delete_cleanup_failure_preserves_database_records() -> None:
    knowledge_base_id = uuid.uuid4()
    document = Document(
        id=uuid.uuid4(), knowledge_base_id=knowledge_base_id, source_object_key="source"
    )
    documents = AsyncMock()
    documents.get_for_update.return_value = document
    tasks = AsyncMock()
    tasks.has_active_task.return_value = False
    session = AsyncMock()
    index = AsyncMock()
    index.delete_document.side_effect = RuntimeError("redis unavailable")
    service = DocumentService(
        AsyncMock(), documents, tasks, session, AsyncMock(), AsyncMock(), index
    )

    with pytest.raises(DocumentCleanupFailedError):
        await service.delete(knowledge_base_id, document.id)

    tasks.delete_by_document.assert_not_awaited()
    documents.delete.assert_not_awaited()
    session.commit.assert_not_awaited()
