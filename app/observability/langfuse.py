from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from functools import lru_cache
from importlib import import_module
from typing import Any, Protocol, cast

from app.config import get_settings


class _LangfuseClient(Protocol):
    def start_as_current_observation(self, **kwargs: object) -> Any: ...

    def flush(self) -> None: ...


def _build_langfuse_client(
    *,
    base_url: str,
    public_key: str,
    secret_key: str,
    environment: str,
) -> _LangfuseClient | None:
    try:  # pragma: no cover - optional dependency
        langfuse_module = import_module("langfuse")
    except Exception:  # pragma: no cover - optional dependency
        return None
    langfuse_class = getattr(langfuse_module, "Langfuse", None)
    if not callable(langfuse_class):
        return None
    return cast(
        _LangfuseClient,
        langfuse_class(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
            environment=environment,
        ),
    )


class LangfuseTracer:
    def __init__(
        self,
        *,
        base_url: str,
        public_key: str,
        secret_key: str,
        environment: str = "default",
    ) -> None:
        self._client = (
            _build_langfuse_client(
                base_url=base_url,
                public_key=public_key,
                secret_key=secret_key,
                environment=environment,
            )
            if base_url and public_key and secret_key
            else None
        )
        self.enabled = self._client is not None

    @contextmanager
    def span(
        self,
        name: str,
        metadata: dict[str, object] | None = None,
        *,
        input: object | None = None,
        output: object | None = None,
        trace_context: dict[str, object] | None = None,
    ) -> Generator[object | None, None, None]:
        if not self.enabled or self._client is None:
            with nullcontext(None) as span:
                yield span
            return

        with self._client.start_as_current_observation(
            as_type="span",
            name=name,
            metadata=metadata or {},
            input=input,
            output=output,
            trace_context=trace_context,
        ) as span:
            yield span

    def flush(self) -> None:
        if self.enabled and self._client is not None:
            self._client.flush()


@lru_cache
def get_langfuse_tracer() -> LangfuseTracer:
    settings = get_settings()
    return LangfuseTracer(
        base_url=settings.langfuse_base_url,
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        environment=settings.langfuse_environment,
    )
