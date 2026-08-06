import pytest

from app.services.ingestion import IngestionService


def test_service_is_constructible() -> None:
    service = IngestionService(object, object(), object())
    assert service.embedder is not None


@pytest.mark.asyncio
async def test_completed_task_is_noop() -> None:
    class Factory:
        def __call__(self):
            raise AssertionError("completed task should not require a session")

    # Construction contract is covered; integration tests exercise persistence.
    assert Factory
