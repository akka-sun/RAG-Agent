import uuid
from datetime import UTC, datetime

import pytest

from app.core.exceptions import (
    DocumentTooLargeError,
    InvalidStatusTransitionError,
    UnsupportedDocumentError,
)
from app.schemas.documents import (
    MAX_DOCUMENT_SIZE,
    DocumentAcceptedResponse,
    DocumentResponse,
    validate_upload,
)
from app.schemas.ingestion_tasks import IngestionTaskResponse, transition_status


def test_validate_upload_contract() -> None:
    assert validate_upload("../folder/Readme.MD", b"x") == "Readme.MD"
    assert validate_upload("a.txt", b"x" * MAX_DOCUMENT_SIZE) == "a.txt"
    with pytest.raises(DocumentTooLargeError):
        validate_upload("a.txt", b"x" * (MAX_DOCUMENT_SIZE + 1))
    for name, content in [(None, b"x"), ("a.pdf", b"x"), ("a.txt", b"")]:
        with pytest.raises(UnsupportedDocumentError):
            validate_upload(name, content)


def test_response_models_serialize_orm_objects() -> None:
    now = datetime.now(UTC)
    doc_id, task_id, kb_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    doc = type(
        "Doc",
        (),
        dict(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename="a.txt",
            content_type="text/plain",
            size_bytes=1,
            source_object_key="x",
            parsed_object_key=None,
            status="pending",
            chunk_count=0,
            error=None,
            created_at=now,
            updated_at=now,
        ),
    )()
    task = type(
        "Task",
        (),
        dict(
            id=task_id,
            document_id=doc_id,
            arq_job_id=None,
            status="pending",
            stage="queued",
            progress=0,
            error=None,
            created_at=now,
            started_at=None,
            completed_at=None,
        ),
    )()
    assert DocumentResponse.model_validate(doc).id == doc_id
    assert IngestionTaskResponse.model_validate(task).document_id == doc_id
    assert (
        DocumentAcceptedResponse(document_id=doc_id, task_id=task_id, status="pending").status
        == "pending"
    )


@pytest.mark.parametrize(
    "current,target",
    [("completed", "pending"), ("failed", "processing"), ("processing", "pending")],
)
def test_invalid_status_transitions(current: str, target: str) -> None:
    with pytest.raises(InvalidStatusTransitionError):
        transition_status(current, target)
