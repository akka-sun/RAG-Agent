import uuid
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate


class KnowledgeBaseError(Exception):
    pass


class KnowledgeBaseNotFoundError(KnowledgeBaseError):
    pass


class KnowledgeBaseNameConflictError(KnowledgeBaseError):
    pass


class KnowledgeBaseRepositoryProtocol(Protocol):
    async def add(self, item: KnowledgeBase) -> KnowledgeBase: ...

    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None: ...

    async def list_all(self) -> list[KnowledgeBase]: ...

    async def delete(self, item: KnowledgeBase) -> None: ...


class KnowledgeBaseService:
    def __init__(
        self,
        repository: KnowledgeBaseRepositoryProtocol,
        session: AsyncSession,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        self._repository = repository
        self._session = session
        self._embedding_model = embedding_model
        self._embedding_dimension = embedding_dimension

    async def create(
        self,
        data: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        item = KnowledgeBase(
            name=data.name,
            description=data.description,
            embedding_model=self._embedding_model,
            embedding_dimension=self._embedding_dimension,
        )

        try:
            await self._repository.add(item)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise KnowledgeBaseNameConflictError from exc

        return item

    async def list_all(self) -> list[KnowledgeBase]:
        return await self._repository.list_all()

    async def get(
        self,
        item_id: uuid.UUID,
    ) -> KnowledgeBase:
        item = await self._repository.get_by_id(item_id)

        if item is None:
            raise KnowledgeBaseNotFoundError

        return item

    async def delete(
        self,
        item_id: uuid.UUID,
    ) -> None:
        item = await self.get(item_id)
        await self._repository.delete(item)
        await self._session.commit()
