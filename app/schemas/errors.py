from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ErrorCode(StrEnum):
    INVALID_STATUS_TRANSITION = "invalid_status_transition"
    DOCUMENT_NOT_FOUND = "document_not_found"
    INGESTION_TASK_NOT_FOUND = "ingestion_task_not_found"
    UNSUPPORTED_DOCUMENT = "unsupported_document"
    DOCUMENT_TOO_LARGE = "document_too_large"
    DOCUMENT_NOT_RETRYABLE = "document_not_retryable"
    DOCUMENT_STORAGE_UNAVAILABLE = "document_storage_unavailable"
    INGESTION_QUEUE_UNAVAILABLE = "ingestion_queue_unavailable"
    DOCUMENT_CLEANUP_FAILED = "document_cleanup_failed"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
