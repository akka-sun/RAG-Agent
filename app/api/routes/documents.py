import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.api.dependencies import DocumentServiceDependency
from app.schemas.documents import (
    MAX_DOCUMENT_SIZE,
    DocumentAcceptedResponse,
)
from app.schemas.errors import ErrorResponse

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/documents",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def upload_document(
    knowledge_base_id: uuid.UUID,
    service: DocumentServiceDependency,
    file: Annotated[UploadFile, File()],
) -> DocumentAcceptedResponse:
    content = await file.read(MAX_DOCUMENT_SIZE + 1)
    document, task = await service.upload(
        knowledge_base_id,
        file.filename or "",
        file.content_type or "application/octet-stream",
        content,
    )
    return DocumentAcceptedResponse(
        document_id=document.id,
        task_id=task.id,
        status="pending",
    )
