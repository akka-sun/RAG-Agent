import os

import pytest

from app.observability import LangfuseTracer
from tests.conftest import skip_unless_external_enabled


@pytest.mark.external
def test_langfuse_tracer_sends_real_span() -> None:
    base_url = os.getenv("RAG_AGENT_LANGFUSE_BASE_URL", "")
    public_key = os.getenv("RAG_AGENT_LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("RAG_AGENT_LANGFUSE_SECRET_KEY", "")
    skip_unless_external_enabled(base_url, public_key, secret_key)

    tracer = LangfuseTracer(
        base_url=base_url,
        public_key=public_key,
        secret_key=secret_key,
        environment=os.getenv("RAG_AGENT_LANGFUSE_ENVIRONMENT", "test"),
    )
    assert tracer.enabled is True
    with tracer.span("rag-agent.external-test", {"stage": "external-test"}):
        pass
    tracer.flush()
