import pytest

from app.worker import WorkerSettings, on_shutdown, on_startup


def test_worker_registers_ingestion_job() -> None:
    assert "ingest_document" in [fn.__name__ for fn in WorkerSettings.functions]


@pytest.mark.asyncio
async def test_worker_hooks_accept_context() -> None:
    ctx: dict[str, object] = {}
    await on_startup(ctx)
    await on_shutdown(ctx)
