from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str | None = None
    stage: str | None = None
    knowledge_base_id: str | None = None
    document_id: str | None = None
    task_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    parser: str | None = None
    retrieval_attempt: int | None = None
    extra: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, object | None]:
        payload: dict[str, object | None] = {
            "trace_id": self.trace_id,
            "stage": self.stage,
            "knowledge_base_id": self.knowledge_base_id,
            "document_id": self.document_id,
            "task_id": self.task_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "parser": self.parser,
            "retrieval_attempt": self.retrieval_attempt,
        }
        if self.extra:
            payload.update(self.extra)
        return payload


_trace_context: ContextVar[TraceContext | None] = ContextVar(
    "rag_agent_trace_context",
    default=None,
)


def get_trace_context() -> TraceContext:
    return _trace_context.get() or TraceContext()


def set_trace_context(
    *,
    trace_id: str | None = None,
    stage: str | None = None,
    knowledge_base_id: str | None = None,
    document_id: str | None = None,
    task_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    parser: str | None = None,
    retrieval_attempt: int | None = None,
    extra: dict[str, Any] | None = None,
) -> Token[TraceContext | None]:
    current = get_trace_context()
    merged_extra = dict(current.extra or {})
    if extra:
        merged_extra.update(extra)
    updated = replace(
        current,
        trace_id=trace_id if trace_id is not None else current.trace_id,
        stage=stage if stage is not None else current.stage,
        knowledge_base_id=(
            knowledge_base_id if knowledge_base_id is not None else current.knowledge_base_id
        ),
        document_id=document_id if document_id is not None else current.document_id,
        task_id=task_id if task_id is not None else current.task_id,
        conversation_id=conversation_id if conversation_id is not None else current.conversation_id,
        message_id=message_id if message_id is not None else current.message_id,
        parser=parser if parser is not None else current.parser,
        retrieval_attempt=(
            retrieval_attempt if retrieval_attempt is not None else current.retrieval_attempt
        ),
        extra=merged_extra or None,
    )
    return _trace_context.set(updated)


def clear_trace_context(token: Token[TraceContext | None]) -> None:
    _trace_context.reset(token)


@contextmanager
def trace_scope(**kwargs: Any) -> Generator[TraceContext, None, None]:
    token = set_trace_context(**kwargs)
    try:
        yield get_trace_context()
    finally:
        clear_trace_context(token)
