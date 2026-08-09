from fastapi import APIRouter, status

from app.api.dependencies import (
    AgentChatServiceDependency,
    HybridRetrievalServiceDependency,
    KnowledgeBaseServiceDependency,
    RAGServiceDependency,
)
from app.schemas.errors import ErrorResponse
from app.schemas.rag import (
    AgentQueryRequest,
    AgentQueryResponse,
    RAGDocumentCreate,
    RAGDocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSourceResponse,
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
    "/agent/query",
    response_model=AgentQueryResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def query_agent(
    data: AgentQueryRequest,
    knowledge_base_service: KnowledgeBaseServiceDependency,
    service: AgentChatServiceDependency,
) -> AgentQueryResponse:
    await knowledge_base_service.get(data.knowledge_base_id)
    answer = await service.answer(
        knowledge_base_id=data.knowledge_base_id,
        query=data.query,
    )
    return AgentQueryResponse(
        answer=answer.content,
        sources=[
            RAGSourceResponse(
                label=item.label,
                document_id=item.document_id,
                filename=item.filename,
                chunk_id=item.chunk_id,
                text=item.text,
                start=item.start,
                end=item.end,
                score=item.score,
                page_number=item.page_number,
                section=item.section,
            )
            for item in answer.citations
        ],
    )


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
    knowledge_base_service: KnowledgeBaseServiceDependency,
    service: HybridRetrievalServiceDependency,
) -> RAGQueryResponse:
    await knowledge_base_service.get(data.knowledge_base_id)
    context = await service.query(
        knowledge_base_id=data.knowledge_base_id,
        query=data.query,
        limit=data.top_k,
    )
    return RAGQueryResponse(
        answer=context.answer,
        sources=[
            RAGSourceResponse(
                label=item.label,
                document_id=item.document_id,
                filename=item.filename,
                chunk_id=item.chunk_id,
                text=item.text,
                start=item.start,
                end=item.end,
                score=item.score,
                page_number=item.page_number,
                section=item.section,
            )
            for item in context.evidence
        ],
    )
