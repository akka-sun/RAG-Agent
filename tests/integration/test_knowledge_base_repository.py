import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import KnowledgeBaseRepository


async def test_repository_add_list_get_and_delete(
    db_session: AsyncSession,
) -> None:
    repository = KnowledgeBaseRepository(db_session)
    item = KnowledgeBase(
        name="产品文档",
        description="产品知识",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
    )

    await repository.add(item)
    await db_session.commit()

    assert await repository.get_by_id(item.id) is item
    assert [row.name for row in await repository.list_all()] == ["产品文档"]

    await repository.delete(item)
    await db_session.commit()

    assert await repository.get_by_id(item.id) is None
    assert await repository.get_by_id(uuid.uuid4()) is None