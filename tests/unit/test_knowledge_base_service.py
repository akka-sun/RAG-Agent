import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.knowledge_base import (
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
)


class FakeRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, KnowledgeBase] = {}

    async def add(self, item: KnowledgeBase) -> KnowledgeBase:
        self.items[item.id] = item
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> KnowledgeBase | None:
        return self.items.get(item_id)

    async def list_all(self) -> list[KnowledgeBase]:
        return list(self.items.values())

    async def delete(self, item: KnowledgeBase) -> None:
        del self.items[item.id]


@pytest.mark.asyncio
async def test_service_create_and_commit() -> None:
    session = AsyncMock(spec=AsyncSession)
    service = KnowledgeBaseService(FakeRepository(), session)

    item = await service.create(
        KnowledgeBaseCreate(
            name="产品文档",
            description="",
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
        )
    )

    assert item.name == "产品文档"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_get_missing_raises_not_found() -> None:
    session = AsyncMock(spec=AsyncSession)
    service = KnowledgeBaseService(FakeRepository(), session)

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.get(uuid.uuid4())


@pytest.mark.asyncio
async def test_service_list_and_delete() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = FakeRepository()
    service = KnowledgeBaseService(repository, session)

    item = KnowledgeBase(
        name="产品文档",
        description="",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
    )
    await repository.add(item)

    assert await service.list_all() == [item]

    await service.delete(item.id)

    assert repository.items == {}
    session.commit.assert_awaited_once()
