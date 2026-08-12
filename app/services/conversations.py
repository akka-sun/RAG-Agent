import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.schemas.conversations import ConversationCreate
from app.services.knowledge_base import KnowledgeBaseNotFoundError


class ConversationError(Exception):
    pass


class ConversationNotFoundError(ConversationError):
    pass


class KnowledgeBaseRepositoryProtocol(Protocol):
    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None: ...


class ConversationRepositoryProtocol(Protocol):
    async def create(self, *, knowledge_base_id: uuid.UUID, title: str) -> Conversation: ...

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None: ...

    async def list_by_knowledge_base(self, knowledge_base_id: uuid.UUID) -> list[Conversation]: ...

    async def delete(self, conversation: Conversation) -> None: ...


class MessageRepositoryProtocol(Protocol):
    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]: ...


class ConversationService:
    def __init__(
        self,
        *,
        knowledge_bases: KnowledgeBaseRepositoryProtocol,
        conversations: ConversationRepositoryProtocol,
        session: AsyncSession,
        messages: MessageRepositoryProtocol | None = None,
    ) -> None:
        self._knowledge_bases = knowledge_bases
        self._conversations = conversations
        self._messages = messages
        self._session = session

    async def create(
        self,
        *,
        knowledge_base_id: uuid.UUID,
        data: ConversationCreate,
    ) -> Conversation:
        await self._ensure_knowledge_base_exists(knowledge_base_id)
        conversation = await self._conversations.create(
            knowledge_base_id=knowledge_base_id,
            title=data.title,
        )
        await self._session.commit()
        return conversation

    async def list_by_knowledge_base(self, knowledge_base_id: uuid.UUID) -> list[Conversation]:
        await self._ensure_knowledge_base_exists(knowledge_base_id)
        return await self._conversations.list_by_knowledge_base(knowledge_base_id)

    async def get(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError
        return conversation

    async def delete(self, conversation_id: uuid.UUID) -> None:
        conversation = await self.get(conversation_id)
        await self._conversations.delete(conversation)
        await self._session.commit()

    async def list_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        await self.get(conversation_id)
        if self._messages is None:
            return []
        return await self._messages.list_by_conversation(conversation_id)

    async def _ensure_knowledge_base_exists(self, knowledge_base_id: uuid.UUID) -> None:
        if await self._knowledge_bases.get_by_id(knowledge_base_id) is None:
            raise KnowledgeBaseNotFoundError
