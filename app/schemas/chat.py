from typing import Literal

from pydantic import BaseModel, Field

SSEEventName = Literal[
    "message_start",
    "agent_status",
    "retrieval_start",
    "retrieval_result",
    "token",
    "citation",
    "message_end",
    "error",
]


class SSEEvent(BaseModel):
    event: SSEEventName
    data: dict[str, object] = Field(default_factory=dict)


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
