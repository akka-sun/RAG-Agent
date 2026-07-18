from typing import Literal, TypedDict

from fastapi import APIRouter, FastAPI

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

    @router.get("/health/live", tags=["系统"])
    async def live_health() -> HealthResponse:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    application.include_router(router)
    return application


app = create_app()
