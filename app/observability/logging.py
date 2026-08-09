from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.observability.context import get_trace_context

_HANDLER_MARKER = "_rag_agent_structured_handler"
_ORIGINAL_RECORD_FACTORY = logging.getLogRecordFactory()
_factory_installed = False


def _record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    record = _ORIGINAL_RECORD_FACTORY(*args, **kwargs)
    for key, value in get_trace_context().as_dict().items():
        prefixed_key = f"rag_{key}"
        if not hasattr(record, prefixed_key):
            setattr(record, prefixed_key, value)
    if not hasattr(record, "trace_id"):
        record.__dict__["trace_id"] = get_trace_context().trace_id
    return record


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object | None] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(get_trace_context().as_dict())
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: int | str = logging.INFO) -> None:
    global _factory_installed
    if not _factory_installed:
        logging.setLogRecordFactory(_record_factory)
        _factory_installed = True
    root = logging.getLogger()
    root.setLevel(level)
    if any(getattr(handler, _HANDLER_MARKER, False) for handler in root.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)
