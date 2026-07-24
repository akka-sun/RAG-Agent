from typing import Literal, TypedDict

from fastapi import APIRouter, FastAPI

from app.api.errors import register_error_handlers
from app.api.routes.knowledge_bases import (
    router as knowledge_bases_router,
)
from app.api.routes.rag import router as rag_router
from app.config import get_settings


class HealthResponse(TypedDict):
    status: Literal["ok"]


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    router = APIRouter(prefix=settings.api_v1_prefix)

    @router.get(
        "/health/live",
        tags=["系统"],
    )
    async def live_health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    router.include_router(knowledge_bases_router)
    router.include_router(rag_router)

    application.include_router(router)
    register_error_handlers(application)

    return application


app = create_app()
