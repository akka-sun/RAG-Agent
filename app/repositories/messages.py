import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message, MessageRole, MessageStatus
from app.models.message_citation import MessageCitation


class CitationValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MessageCitationInput:
    source_label: str
    document_id: uuid.UUID
    chunk_id: str
    quote: str
    page_number: int | None = None
    section: str | None = None
    score: float | None = None
    metadata: dict[str, object] = field(default_factory=lambda: {})


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_user_message(self, *, conversation_id: uuid.UUID, content: str) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            status=MessageStatus.COMPLETED,
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def add_assistant_message_with_citations(
        self,
        *,
        conversation_id: uuid.UUID,
        content: str,
        citations: list[MessageCitationInput],
        valid_labels: set[str],
        token_count: int | None = None,
    ) -> Message:
        invalid_labels = [
            item.source_label for item in citations if item.source_label not in valid_labels
        ]
        if invalid_labels:
            msg = f"invalid citation labels: {', '.join(sorted(set(invalid_labels)))}"
            raise CitationValidationError(msg)

        message = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            status=MessageStatus.COMPLETED,
            token_count=token_count,
        )
        message.citations = [
            MessageCitation(
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                source_label=item.source_label,
                quote=item.quote,
                page_number=item.page_number,
                section=item.section,
                score=item.score,
                metadata_json=item.metadata,
            )
            for item in citations
        ]
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        statement = (
            select(Message)
            .options(selectinload(Message.citations))
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence_number.asc())
        )
        result = await self._session.scalars(statement)
        return list(result.all())
