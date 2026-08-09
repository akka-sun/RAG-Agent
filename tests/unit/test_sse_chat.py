import uuid
from dataclasses import dataclass
from typing import Any, cast

import pytest

from app.agent.state import AgentEvidence
from app.repositories.messages import MessageCitationInput
from app.schemas.chat import SSEEvent
from app.services.agent_chat import AgentAnswer
from app.services.sse_chat import ConversationRecordProtocol, SSEChatService, format_sse


class FakeAgentChatService:
    async def answer(self, *, knowledge_base_id: uuid.UUID, query: str) -> AgentAnswer:
        del query
        return AgentAnswer(
            content="hello world",
            citations=[
                AgentEvidence(
                    label="S1",
                    document_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    filename="policy.md",
                    chunk_id="chunk-1",
                    text="quoted evidence",
                    start=0,
                    end=15,
                    score=0.95,
                )
            ],
        )


@dataclass
class ConversationRecord:
    id: uuid.UUID
    knowledge_base_id: uuid.UUID


class FakeConversationRepository:
    def __init__(self, knowledge_base_id: uuid.UUID) -> None:
        self.knowledge_base_id = knowledge_base_id

    async def get(self, conversation_id: uuid.UUID) -> ConversationRecordProtocol | None:
        return ConversationRecord(id=conversation_id, knowledge_base_id=self.knowledge_base_id)


class FakeMessageRepository:
    def __init__(self) -> None:
        self.user_messages: list[tuple[uuid.UUID, str]] = []
        self.assistant_messages: list[tuple[uuid.UUID, str, list[str], set[str]]] = []

    async def add_user_message(self, *, conversation_id: uuid.UUID, content: str) -> object:
        self.user_messages.append((conversation_id, content))
        return object()

    async def add_assistant_message_with_citations(
        self,
        *,
        conversation_id: uuid.UUID,
        content: str,
        citations: list[MessageCitationInput],
        valid_labels: set[str],
        token_count: int | None = None,
    ) -> object:
        del token_count
        self.assistant_messages.append(
            (
                conversation_id,
                content,
                [citation.source_label for citation in citations],
                valid_labels,
            )
        )
        return object()


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


def test_format_sse_serializes_event_name_and_json_data() -> None:
    event = SSEEvent(event="token", data={"text": "hello"})

    assert format_sse(event) == 'event: token\ndata: {"text":"hello"}\n\n'


def test_sse_event_rejects_unknown_event_name() -> None:
    with pytest.raises(ValueError):
        SSEEvent(event=cast(Any, "unknown"), data={})


@pytest.mark.asyncio
async def test_sse_chat_stream_persists_final_message_and_citation() -> None:
    conversation_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    messages = FakeMessageRepository()
    session = FakeSession()
    service = SSEChatService(
        conversations=FakeConversationRepository(knowledge_base_id),
        messages=messages,
        agent=FakeAgentChatService(),
        session=session,
    )

    events = [
        event
        async for event in service.stream(
            conversation_id=conversation_id,
            user_message="Explain policy",
        )
    ]

    assert [event.event for event in events] == [
        "message_start",
        "agent_status",
        "token",
        "token",
        "citation",
        "message_end",
    ]
    assert messages.user_messages == [(conversation_id, "Explain policy")]
    assert messages.assistant_messages == [(conversation_id, "hello world", ["S1"], {"S1"})]
    assert session.commits == 1
