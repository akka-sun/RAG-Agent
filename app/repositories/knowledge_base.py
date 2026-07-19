import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: KnowledgeBase) -> KnowledgeBase:
        self._session.add(item)
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def get_by_id(
        self,
        item_id: uuid.UUID,
    ) -> KnowledgeBase | None:
        return await self._session.get(KnowledgeBase, item_id)

    async def list_all(self) -> list[KnowledgeBase]:
        statement = select(KnowledgeBase).order_by(
            KnowledgeBase.created_at.asc(),
            KnowledgeBase.id.asc(),
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def delete(self, item: KnowledgeBase) -> None:
        await self._session.delete(item)
        await self._session.flush()