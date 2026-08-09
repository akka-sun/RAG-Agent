import json
import uuid
from collections.abc import AsyncIterator
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentEvidence
from app.repositories.messages import MessageCitationInput
from app.schemas.chat import SSEEvent
from app.services.agent_chat import AgentAnswer
from app.services.conversations import ConversationNotFoundError


class ConversationRecordProtocol(Protocol):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID


class ConversationRepositoryProtocol(Protocol):
    async def get(self, conversation_id: uuid.UUID) -> ConversationRecordProtocol | None: ...


class MessageRepositoryProtocol(Protocol):
    async def add_user_message(self, *, conversation_id: uuid.UUID, content: str) -> object: ...

    async def add_assistant_message_with_citations(
        self,
        *,
        conversation_id: uuid.UUID,
        content: str,
        citations: list[MessageCitationInput],
        valid_labels: set[str],
        token_count: int | None = None,
    ) -> object: ...


class AgentChatServiceProtocol(Protocol):
    async def answer(self, *, knowledge_base_id: uuid.UUID, query: str) -> AgentAnswer: ...


class SessionProtocol(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class SSEChatService:
    def __init__(
        self,
        *,
        conversations: ConversationRepositoryProtocol,
        messages: MessageRepositoryProtocol,
        agent: AgentChatServiceProtocol,
        session: SessionProtocol | AsyncSession,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._agent = agent
        self._session = session

    async def stream(
        self,
        *,
        conversation_id: uuid.UUID,
        user_message: str,
    ) -> AsyncIterator[SSEEvent]:
        try:
            conversation = await self._conversations.get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError

            await self._messages.add_user_message(
                conversation_id=conversation_id,
                content=user_message,
            )
            yield SSEEvent(
                event="message_start",
                data={"conversation_id": str(conversation_id)},
            )
            yield SSEEvent(event="agent_status", data={"status": "running"})

            answer = await self._agent.answer(
                knowledge_base_id=conversation.knowledge_base_id,
                query=user_message,
            )
            tokens = _tokens(answer.content)
            for token in tokens:
                yield SSEEvent(event="token", data={"text": token})
            for citation in answer.citations:
                yield SSEEvent(event="citation", data=_citation_event_data(citation))

            citation_inputs = [_citation_input(citation) for citation in answer.citations]
            valid_labels = {citation.label for citation in answer.citations}
            await self._messages.add_assistant_message_with_citations(
                conversation_id=conversation_id,
                content=answer.content,
                citations=citation_inputs,
                valid_labels=valid_labels,
                token_count=len(tokens),
            )
            await self._session.commit()
            yield SSEEvent(event="message_end", data={"content": answer.content})
        except Exception as exc:
            await self._session.rollback()
            yield SSEEvent(event="error", data={"message": str(exc) or exc.__class__.__name__})


def format_sse(event: SSEEvent) -> str:
    payload = json.dumps(
        event.data,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event.event}\ndata: {payload}\n\n"


def _tokens(content: str) -> list[str]:
    return content.split()


def _citation_input(citation: AgentEvidence) -> MessageCitationInput:
    return MessageCitationInput(
        source_label=citation.label,
        document_id=citation.document_id,
        chunk_id=citation.chunk_id,
        quote=citation.text,
        page_number=citation.page_number,
        section=citation.section,
        score=citation.score,
        metadata={
            "filename": citation.filename,
            "start": citation.start,
            "end": citation.end,
            **dict(citation.metadata),
        },
    )


def _citation_event_data(citation: AgentEvidence) -> dict[str, object]:
    return {
        "source_label": citation.label,
        "document_id": str(citation.document_id),
        "chunk_id": citation.chunk_id,
        "quote": citation.text,
        "page_number": citation.page_number,
        "section": citation.section,
        "score": citation.score,
    }
