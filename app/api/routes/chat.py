import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.dependencies import SSEChatServiceDependency
from app.schemas.chat import ChatMessageCreate
from app.schemas.errors import ErrorResponse
from app.services.sse_chat import format_sse

router = APIRouter(
    prefix="/conversations",
    tags=["对话"],
)


@router.post(
    "/{conversation_id}/messages/stream",
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def stream_conversation_message(
    conversation_id: uuid.UUID,
    data: ChatMessageCreate,
    service: SSEChatServiceDependency,
) -> StreamingResponse:
    async def event_body() -> AsyncIterator[str]:
        async for event in service.stream(
            conversation_id=conversation_id,
            user_message=data.content,
        ):
            yield format_sse(event)

    return StreamingResponse(
        event_body(),
        media_type="text/event-stream",
    )
