from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.exceptions import InvalidStatusTransitionError

TaskStatus = Literal["pending", "processing", "completed", "failed"]
_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing"},
    "processing": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


def transition_status(current: str, target: str) -> str:
    if target not in _TRANSITIONS.get(current, set()):
        raise InvalidStatusTransitionError(f"invalid transition: {current} -> {target}")
    return target


class IngestionTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    arq_job_id: str | None = None
    status: TaskStatus
    stage: str
    progress: int
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
