import pytest

from app.observability import (
    clear_trace_context,
    configure_logging,
    get_trace_context,
    set_trace_context,
)


def test_trace_context_round_trip() -> None:
    token = set_trace_context(trace_id="trace-1", knowledge_base_id="kb-1")

    assert get_trace_context().trace_id == "trace-1"
    assert get_trace_context().knowledge_base_id == "kb-1"

    clear_trace_context(token)
    assert get_trace_context().trace_id is None


def test_structured_logging_includes_trace_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging()
    token = set_trace_context(trace_id="trace-2", stage="parse")
    try:
        import logging

        logger = logging.getLogger("rag-agent.test")
        with caplog.at_level("INFO"):
            logger.info("structured log")
    finally:
        clear_trace_context(token)

    assert any(getattr(record, "trace_id", None) == "trace-2" for record in caplog.records)
