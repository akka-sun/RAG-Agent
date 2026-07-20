import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    embedding_model: str = Field(min_length=1, max_length=200)
    embedding_dimension: int = Field(gt=0)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    embedding_model: str
    embedding_dimension: int
    created_at: datetime
    updated_at: datetime
