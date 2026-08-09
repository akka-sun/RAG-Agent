import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.knowledge_base import KnowledgeBase
from app.schemas.conversations import ConversationCreate
from app.services.conversations import ConversationService
from app.services.knowledge_base import KnowledgeBaseNotFoundError


class MissingKnowledgeBaseRepository:
    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None:
        del item_id
        return None


class ExistingKnowledgeBaseRepository:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None:
        if item_id == self.knowledge_base.id:
            return self.knowledge_base
        return None


class FakeConversationRepository:
    def __init__(self) -> None:
        self.created: list[Conversation] = []

    async def create(self, *, knowledge_base_id: uuid.UUID, title: str) -> Conversation:
        conversation = Conversation(knowledge_base_id=knowledge_base_id, title=title)
        self.created.append(conversation)
        return conversation

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return next((item for item in self.created if item.id == conversation_id), None)

    async def list_by_knowledge_base(self, knowledge_base_id: uuid.UUID) -> list[Conversation]:
        return [item for item in self.created if item.knowledge_base_id == knowledge_base_id]

    async def delete(self, conversation: Conversation) -> None:
        self.created.remove(conversation)


@pytest.mark.asyncio
async def test_create_conversation_requires_existing_knowledge_base() -> None:
    service = ConversationService(
        knowledge_bases=MissingKnowledgeBaseRepository(),
        conversations=FakeConversationRepository(),
        session=AsyncMock(spec=AsyncSession),
    )

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.create(
            knowledge_base_id=uuid.uuid4(),
            data=ConversationCreate(title="Chat"),
        )


@pytest.mark.asyncio
async def test_create_conversation_commits_trimmed_title() -> None:
    session = AsyncMock(spec=AsyncSession)
    knowledge_base = KnowledgeBase(
        name="kb",
        description="",
        embedding_model="hashing",
        embedding_dimension=16,
    )
    repository = FakeConversationRepository()
    service = ConversationService(
        knowledge_bases=ExistingKnowledgeBaseRepository(knowledge_base),
        conversations=repository,
        session=session,
    )

    conversation = await service.create(
        knowledge_base_id=knowledge_base.id,
        data=ConversationCreate(title="  Chat  "),
    )

    assert conversation.title == "Chat"
    assert repository.created == [conversation]
    session.commit.assert_awaited_once()
