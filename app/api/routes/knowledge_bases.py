import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import KnowledgeBaseServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["知识库"],
)


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    service: KnowledgeBaseServiceDependency,
) -> KnowledgeBaseResponse:
    item = await service.create(data)
    return KnowledgeBaseResponse.model_validate(item)


@router.get(
    "",
    response_model=list[KnowledgeBaseResponse],
)
async def list_knowledge_bases(
    service: KnowledgeBaseServiceDependency,
) -> list[KnowledgeBaseResponse]:
    items = await service.list_all()
    return [KnowledgeBaseResponse.model_validate(item) for item in items]


@router.get(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def get_knowledge_base(
    knowledge_base_id: uuid.UUID,
    service: KnowledgeBaseServiceDependency,
) -> KnowledgeBaseResponse:
    item = await service.get(knowledge_base_id)
    return KnowledgeBaseResponse.model_validate(item)


@router.delete(
    "/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def delete_knowledge_base(
    knowledge_base_id: uuid.UUID,
    service: KnowledgeBaseServiceDependency,
) -> Response:
    await service.delete(knowledge_base_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
