import ntpath
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.exceptions import DocumentTooLargeError, UnsupportedDocumentError

ALLOWED_DOCUMENT_SUFFIXES = {".md", ".txt"}
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
SAFE_CONTENT_TYPES = {"text/plain", "text/markdown"}


def normalize_content_type(content_type: str | None) -> str:
    if not content_type or "\r" in content_type or "\n" in content_type:
        return "application/octet-stream"
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    return media_type if media_type in SAFE_CONTENT_TYPES else "application/octet-stream"


def validate_upload(filename: str | None, content: bytes) -> str:
    if not filename or "\x00" in filename:
        raise UnsupportedDocumentError("filename is required")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_SUFFIXES or not content:
        raise UnsupportedDocumentError("only non-empty .md and .txt files are supported")
    if len(content) > MAX_DOCUMENT_SIZE:
        raise DocumentTooLargeError("document exceeds 5 MiB")
    basename = ntpath.basename(filename)
    if not basename:
        raise UnsupportedDocumentError("filename basename is required")
    return basename


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
    created_at: datetime
    updated_at: datetime
