import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> None:
        self._session.add(document)
        await self._session.flush()

    async def get(
        self,
        document_id: uuid.UUID,
        knowledge_base_id: uuid.UUID | None = None,
    ) -> Document | None:
        statement = select(Document).where(Document.id == document_id)
        if knowledge_base_id is not None:
            statement = statement.where(Document.knowledge_base_id == knowledge_base_id)
        return await self._session.scalar(statement)

    async def list_by_knowledge_base(
        self,
        knowledge_base_id: uuid.UUID,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.asc(), Document.id.asc())
        )
        result = await self._session.scalars(statement)
        return list(result.all())

    async def get_for_update(
        self, document_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> Document | None:
        return await self._session.scalar(
            select(Document)
            .where(
                Document.id == document_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .with_for_update()
        )

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.flush()
