from typing import Literal

from pydantic import BaseModel, Field

ServiceName = Literal["postgresql", "redis", "minio", "milvus"]
ServiceStatus = Literal["healthy", "unhealthy"]
ReadinessStatus = Literal["healthy", "degraded"]


class ServiceReadiness(BaseModel):
    status: ServiceStatus
    latency_ms: float = Field(ge=0)
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: ReadinessStatus
    services: dict[ServiceName, ServiceReadiness]
