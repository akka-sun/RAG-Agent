import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_task import IngestionTask, TaskStatus


class IngestionTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: IngestionTask) -> None:
        self._session.add(task)
        await self._session.flush()

    async def get(self, task_id: uuid.UUID) -> IngestionTask | None:
        return await self._session.get(IngestionTask, task_id)

    async def claim_pending(self, task_id: uuid.UUID) -> IngestionTask | None:
        statement = (
            update(IngestionTask)
            .where(
                IngestionTask.id == task_id,
                IngestionTask.status == TaskStatus.PENDING,
            )
            .values(status=TaskStatus.PROCESSING, started_at=func.now())
            .returning(IngestionTask)
        )
        return await self._session.scalar(statement)

    async def has_active_task(self, document_id: uuid.UUID) -> bool:
        statement = select(
            select(IngestionTask.id)
            .where(
                IngestionTask.document_id == document_id,
                IngestionTask.status.in_((TaskStatus.PENDING, TaskStatus.PROCESSING)),
            )
            .exists()
        )
        return bool(await self._session.scalar(statement))
