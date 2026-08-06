class DocumentError(Exception):
    code = "document_error"


class UnsupportedDocumentError(DocumentError):
    code = "unsupported_document"


class DocumentTooLargeError(DocumentError):
    code = "document_too_large"


class InvalidStatusTransitionError(DocumentError):
    code = "invalid_status_transition"


class DocumentNotFoundError(DocumentError):
    code = "document_not_found"


class IngestionTaskNotFoundError(DocumentError):
    code = "ingestion_task_not_found"


class IngestionQueueUnavailableError(DocumentError):
    code = "ingestion_queue_unavailable"


class DocumentStorageUnavailableError(DocumentError):
    code = "document_storage_unavailable"


class DocumentCleanupFailedError(DocumentError):
    code = "document_cleanup_failed"


class ParsedDocumentNotReadyError(DocumentError):
    code = "parsed_document_not_ready"


class DocumentNotRetryableError(InvalidStatusTransitionError):
    code = "document_not_retryable"
