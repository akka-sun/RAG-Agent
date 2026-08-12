import uuid
from io import BytesIO
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import DocumentServiceDependency
from app.models.document import Document
from app.models.ingestion_task import IngestionTask
from app.schemas.documents import (
    MAX_DOCUMENT_SIZE,
    DocumentAcceptedResponse,
    DocumentResponse,
)
from app.schemas.errors import ErrorResponse
from app.schemas.ingestion_tasks import IngestionTaskResponse

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
    parser: Annotated[str | None, Form()] = None,
) -> DocumentAcceptedResponse:
    content = await file.read(MAX_DOCUMENT_SIZE + 1)
    document, task = await service.upload(
        knowledge_base_id,
        file.filename or "",
        file.content_type or "application/octet-stream",
        content,
        parser_name=parser,
    )
    return DocumentAcceptedResponse(
        document_id=document.id,
        task_id=task.id,
        status="pending",
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    knowledge_base_id: uuid.UUID, service: DocumentServiceDependency
) -> list[Document]:
    return await service.list_documents(knowledge_base_id)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> Document:
    return await service.get_document(knowledge_base_id, document_id)


@router.get("/{document_id}/source")
async def download_source(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> StreamingResponse:
    filename, content_type, content = await service.download_source(knowledge_base_id, document_id)
    return StreamingResponse(
        BytesIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/{document_id}/parsed")
async def download_parsed(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> Response:
    content = await service.download_parsed(knowledge_base_id, document_id)
    return Response(content=content, media_type="application/json")


@router.get("/{document_id}/images/{asset_index}")
async def download_image(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    asset_index: int,
    service: DocumentServiceDependency,
) -> Response:
    mime_type, content = await service.download_image(
        knowledge_base_id,
        document_id,
        asset_index,
    )
    return Response(content=content, media_type=mime_type)


@router.post(
    "/{document_id}/retry",
    response_model=IngestionTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_document(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> IngestionTask:
    return await service.retry(knowledge_base_id, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentServiceDependency,
) -> None:
    await service.delete(knowledge_base_id, document_id)
