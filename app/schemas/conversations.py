import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCitationResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_id: str
    source_label: str
    quote: str
    page_number: int | None
    section: str | None
    score: float | None
    metadata: dict[str, object] = Field(default_factory=dict)


def _empty_citations() -> list[MessageCitationResponse]:
    return []


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str
    created_at: datetime
    token_count: int | None
    citations: list[MessageCitationResponse] = Field(default_factory=_empty_citations)
