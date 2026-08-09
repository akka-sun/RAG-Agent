from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Literal, TypedDict

from fastapi import APIRouter, FastAPI

from app.agent.checkpoint import ensure_langgraph_security_env, setup_checkpointer
from app.api.errors import register_error_handlers
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.ingestion_tasks import router as ingestion_tasks_router
from app.api.routes.knowledge_bases import (
    router as knowledge_bases_router,
)
from app.api.routes.rag import router as rag_router
from app.config import get_settings


class HealthResponse(TypedDict):
    status: Literal["ok"]


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        del application
        ensure_langgraph_security_env(strict_msgpack=settings.langgraph_strict_msgpack)
        await setup_checkpointer(
            settings.database_url,
            strict_msgpack=settings.langgraph_strict_msgpack,
        )
        yield

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    router = APIRouter(prefix=settings.api_v1_prefix)

    @router.get(
        "/health/live",
        tags=["系统"],
    )
    async def live_health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    router.include_router(knowledge_bases_router)
    router.include_router(conversations_router)
    router.include_router(documents_router)
    router.include_router(ingestion_tasks_router)
    router.include_router(rag_router)

    application.include_router(router)
    register_error_handlers(application)

    return application


app = create_app()
