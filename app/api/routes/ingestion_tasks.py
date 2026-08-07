import uuid

from fastapi import APIRouter

from app.api.dependencies import DocumentServiceDependency
from app.models.ingestion_task import IngestionTask
from app.schemas.ingestion_tasks import IngestionTaskResponse

router = APIRouter(prefix="/ingestion-tasks", tags=["ingestion-tasks"])


@router.get("/{task_id}", response_model=IngestionTaskResponse)
async def get_ingestion_task(
    task_id: uuid.UUID, service: DocumentServiceDependency
) -> IngestionTask:
    return await service.get_task(task_id)
