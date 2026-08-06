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

