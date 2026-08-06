from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.exceptions import DocumentTooLargeError, UnsupportedDocumentError

ALLOWED_DOCUMENT_SUFFIXES = {".md", ".txt"}
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024


def validate_upload(filename: str | None, content: bytes) -> str:
    if not filename:
        raise UnsupportedDocumentError("filename is required")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_SUFFIXES or not content:
        raise UnsupportedDocumentError("only non-empty .md and .txt files are supported")
    if len(content) > MAX_DOCUMENT_SIZE:
        raise DocumentTooLargeError("document exceeds 5 MiB")
    return Path(filename).name


class DocumentAcceptedResponse(BaseModel):
    document_id: UUID
    task_id: UUID
    status: Literal["pending"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    knowledge_base_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    source_object_key: str
    parsed_object_key: str | None = None
    status: str
    chunk_count: int
    error: str | None = None
    created_at: object
    updated_at: object
