from typing import Protocol
from uuid import UUID

from arq.connections import ArqRedis

from app.core.exceptions import IngestionQueueUnavailableError


class IngestionQueue(Protocol):
    async def enqueue(self, task_id: UUID, document_id: UUID) -> str: ...


class ArqIngestionQueue:
    def __init__(self, redis: ArqRedis) -> None:
        self.redis = redis

    async def enqueue(self, task_id: UUID, document_id: UUID) -> str:
        try:
            job = await self.redis.enqueue_job(
                "ingest_document",
                str(task_id),
                str(document_id),
                _job_id=str(task_id),
            )
        except Exception as exc:
            raise IngestionQueueUnavailableError("Ingestion queue is unavailable") from exc

        if job is None:
            raise IngestionQueueUnavailableError("Ingestion task is already queued")
        return job.job_id
