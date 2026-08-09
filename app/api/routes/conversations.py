import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import ConversationServiceDependency
from app.models.message import Message
from app.schemas.conversations import (
    ConversationCreate,
    ConversationResponse,
    MessageCitationResponse,
    MessageResponse,
)
from app.schemas.errors import ErrorResponse

router = APIRouter(
    tags=["会话"],
)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_conversation(
    knowledge_base_id: uuid.UUID,
    data: ConversationCreate,
    service: ConversationServiceDependency,
) -> ConversationResponse:
    conversation = await service.create(
        knowledge_base_id=knowledge_base_id,
        data=data,
    )
    return ConversationResponse.model_validate(conversation)


@router.get(
    "/knowledge-bases/{knowledge_base_id}/conversations",
    response_model=list[ConversationResponse],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def list_conversations(
    knowledge_base_id: uuid.UUID,
    service: ConversationServiceDependency,
) -> list[ConversationResponse]:
    conversations = await service.list_by_knowledge_base(knowledge_base_id)
    return [ConversationResponse.model_validate(item) for item in conversations]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def get_conversation(
    conversation_id: uuid.UUID,
    service: ConversationServiceDependency,
) -> ConversationResponse:
    conversation = await service.get(conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    service: ConversationServiceDependency,
) -> Response:
    await service.delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    service: ConversationServiceDependency,
) -> list[MessageResponse]:
    messages = await service.list_messages(conversation_id)
    return [_message_response(message) for message in messages]


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at,
        token_count=message.token_count,
        citations=[
            MessageCitationResponse(
                id=citation.id,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                source_label=citation.source_label,
                quote=citation.quote,
                page_number=citation.page_number,
                section=citation.section,
                score=citation.score,
                metadata=citation.metadata_json,
            )
            for citation in message.citations
        ],
    )
