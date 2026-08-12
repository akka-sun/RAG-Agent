import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, knowledge_base_id: uuid.UUID, title: str) -> Conversation:
        conversation = Conversation(knowledge_base_id=knowledge_base_id, title=title)
        self._session.add(conversation)
        await self._session.flush()
        await self._session.refresh(conversation)
        return conversation

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def list_by_knowledge_base(self, knowledge_base_id: uuid.UUID) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.knowledge_base_id == knowledge_base_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.asc())
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def delete(self, conversation: Conversation) -> None:
        await self._session.delete(conversation)
        await self._session.flush()
