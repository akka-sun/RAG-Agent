from fastapi import APIRouter, status

from app.api.dependencies import RAGServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.rag import (
    RAGDocumentCreate,
    RAGDocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)

router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)


@router.post(
    "/documents",
    response_model=RAGDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def ingest_document(
    data: RAGDocumentCreate,
    service: RAGServiceDependency,
) -> RAGDocumentResponse:
    return await service.ingest(data)


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def query_rag(
    data: RAGQueryRequest,
    service: RAGServiceDependency,
) -> RAGQueryResponse:
    return await service.query(data)
