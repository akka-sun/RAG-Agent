from app.observability import LangfuseTracer


def test_langfuse_tracer_is_disabled_without_credentials() -> None:
    tracer = LangfuseTracer(base_url="", public_key="", secret_key="")

    assert tracer.enabled is False
    with tracer.span("retrieve", {"document_id": "d1"}) as span:
        assert span is None
