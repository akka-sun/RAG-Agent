import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.knowledge_base import (
    KnowledgeBaseNameConflictError,
    KnowledgeBaseNotFoundError,
)

logger = logging.getLogger(__name__)


def error_body(
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(KnowledgeBaseNotFoundError)
    async def handle_not_found(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        exc: KnowledgeBaseNotFoundError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=404,
            content=error_body(
                "knowledge_base_not_found",
                "知识库不存在",
            ),
        )

    @app.exception_handler(KnowledgeBaseNameConflictError)
    async def handle_conflict(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        exc: KnowledgeBaseNameConflictError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=409,
            content=error_body(
                "knowledge_base_name_conflict",
                "知识库名称已存在",
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                error_body(
                    "validation_error",
                    "请求参数校验失败",
                    exc.errors(),
                )
            ),
        )

    @app.exception_handler(Exception)
    async def handle_internal_error(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        del request
        logger.error("未处理的 API 异常", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body(
                "internal_error",
                "服务器内部错误",
            ),
        )