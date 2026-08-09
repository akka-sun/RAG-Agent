import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Literal, TypedDict

from fastapi import APIRouter, FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.agent.checkpoint import ensure_langgraph_security_env, setup_checkpointer
from app.api.errors import register_error_handlers
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.ingestion_tasks import router as ingestion_tasks_router
from app.api.routes.knowledge_bases import (
    router as knowledge_bases_router,
)
from app.api.routes.rag import router as rag_router
from app.config import get_settings
from app.observability import clear_trace_context, configure_logging, set_trace_context

logger = logging.getLogger(__name__)


class HealthResponse(TypedDict):
    status: Literal["ok"]


async def trace_requests(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
    token = set_trace_context(trace_id=trace_id, stage="http")
    logger.info("http request started", extra={"path": request.url.path, "method": request.method})
    try:
        response = await call_next(request)
    except Exception:
        clear_trace_context(token)
        raise
    response.headers["x-trace-id"] = trace_id
    logger.info(
        "http request finished",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
        },
    )
    clear_trace_context(token)
    return response


def create_app() -> FastAPI:
    configure_logging()
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

    application.middleware("http")(trace_requests)

    router = APIRouter(prefix=settings.api_v1_prefix)

    @router.get(
        "/health/live",
        tags=["系统"],
    )
    async def live_health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    router.include_router(knowledge_bases_router)
    router.include_router(conversations_router)
    router.include_router(chat_router)
    router.include_router(documents_router)
    router.include_router(ingestion_tasks_router)
    router.include_router(rag_router)

    application.include_router(router)
    register_error_handlers(application)

    return application


app = create_app()
