import uuid

import pytest
from pydantic import ValidationError

from app.schemas.rag import (
    RAGDocumentCreate,
    RAGQueryRequest,
)


def test_document_create_accepts_markdown_and_strips_filename() -> None:
    data = RAGDocumentCreate(
        knowledge_base_id=uuid.uuid4(),
        filename=" notes.MD ",
        content="knowledge",
    )

    assert data.filename == "notes.MD"


@pytest.mark.parametrize(
    "filename",
    [
        "notes.pdf",
        "notes",
        "   ",
    ],
)
def test_document_create_rejects_unsupported_filename(
    filename: str,
) -> None:
    with pytest.raises(ValidationError):
        RAGDocumentCreate(
            knowledge_base_id=uuid.uuid4(),
            filename=filename,
            content="knowledge",
        )


def test_document_create_rejects_blank_content() -> None:
    with pytest.raises(ValidationError):
        RAGDocumentCreate(
            knowledge_base_id=uuid.uuid4(),
            filename="notes.txt",
            content="   ",
        )


def test_query_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        RAGQueryRequest(
            knowledge_base_id=uuid.uuid4(),
            query="   ",
        )


@pytest.mark.parametrize(
    "top_k",
    [
        0,
        11,
    ],
)
def test_query_rejects_top_k_outside_supported_range(
    top_k: int,
) -> None:
    with pytest.raises(ValidationError):
        RAGQueryRequest(
            knowledge_base_id=uuid.uuid4(),
            query="database",
            top_k=top_k,
        )
