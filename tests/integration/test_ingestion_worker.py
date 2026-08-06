import pytest

from app.worker import ingest_document


@pytest.mark.asyncio
async def test_worker_delegates_to_ingestion_service():
    class Service:
        def __init__(self): self.calls = []
        async def run(self, task_id, document_id): self.calls.append((task_id, document_id))

    service = Service()
    await ingest_document({"ingestion_service": service}, "task-1", "doc-1")
    assert service.calls == [("task-1", "doc-1")]


@pytest.mark.asyncio
async def test_worker_propagates_service_error():
    class Service:
        async def run(self, *_): raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await ingest_document({"ingestion_service": Service()}, "t", "d")
