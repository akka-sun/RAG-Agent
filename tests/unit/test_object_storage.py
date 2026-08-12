from __future__ import annotations

import asyncio
import io
import threading
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest

from app.infrastructure.object_storage import (
    MinioObjectStorage,
    image_asset_key,
    parsed_key,
    source_key,
)

KB_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeResponse:
    def __init__(self, data: bytes = b"document", error: Exception | None = None) -> None:
        self.data = data
        self.error = error
        self.closed = False
        self.released = False

    def read(self) -> bytes:
        if self.error is not None:
            raise self.error
        return self.data

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class FakeMinio:
    def __init__(self, *, bucket_exists: bool = True, response: FakeResponse | None = None) -> None:
        self.exists = bucket_exists
        self.response = response or FakeResponse()
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def bucket_exists(self, bucket: str) -> bool:
        self.calls.append(("bucket_exists", (bucket,), {}))
        return self.exists

    def make_bucket(self, bucket: str) -> None:
        self.calls.append(("make_bucket", (bucket,), {}))
        self.exists = True

    def put_object(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("put_object", args, kwargs))

    def get_object(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get_object", args, kwargs))
        return self.response

    def remove_object(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("remove_object", args, kwargs))


def test_object_keys_are_stable_and_strip_all_path_components() -> None:
    expected_prefix = (
        "knowledge-bases/11111111-1111-1111-1111-111111111111/"
        "documents/22222222-2222-2222-2222-222222222222"
    )

    assert source_key(KB_ID, DOCUMENT_ID, "../../secrets/report.pdf") == (
        f"{expected_prefix}/source/report.pdf"
    )
    assert source_key(KB_ID, DOCUMENT_ID, r"C:\temp\report.pdf") == (
        f"{expected_prefix}/source/report.pdf"
    )
    assert parsed_key(KB_ID, DOCUMENT_ID) == f"{expected_prefix}/parsed.json"
    assert image_asset_key(KB_ID, DOCUMENT_ID, 12, "images/chart.png", "image/png") == (
        f"{expected_prefix}/images/0012.png"
    )


def test_image_asset_key_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="asset_index"):
        image_asset_key(KB_ID, DOCUMENT_ID, -1, "image.png", "image/png")


@pytest.mark.parametrize("filename", ["", ".", "..", "folder/", "folder\\"])
def test_source_key_rejects_filename_without_a_basename(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        source_key(KB_ID, DOCUMENT_ID, filename)


@pytest.mark.asyncio
async def test_put_initializes_bucket_and_passes_stream_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeMinio(bucket_exists=False)
    calls: list[Callable[..., Any]] = []

    async def fake_to_thread(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        calls.append(function)
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    storage = MinioObjectStorage(client, "documents")

    await storage.put("source/key", b"hello", "text/plain")

    assert calls == [client.bucket_exists, client.make_bucket, client.put_object]
    _, args, kwargs = client.calls[-1]
    assert args[:2] == ("documents", "source/key")
    assert isinstance(args[2], io.BytesIO)
    assert args[2].read() == b"hello"
    assert kwargs == {"length": 5, "content_type": "text/plain"}


@pytest.mark.asyncio
async def test_concurrent_operations_initialize_bucket_once() -> None:
    client = FakeMinio(bucket_exists=False)
    storage = MinioObjectStorage(client, "documents")

    await asyncio.gather(storage.delete("one"), storage.delete("two"))

    assert [call[0] for call in client.calls].count("bucket_exists") == 1
    assert [call[0] for call in client.calls].count("make_bucket") == 1
    assert [call[0] for call in client.calls].count("remove_object") == 2


@pytest.mark.asyncio
async def test_get_returns_bytes_and_always_releases_response() -> None:
    response = FakeResponse(b"stored bytes")
    storage = MinioObjectStorage(FakeMinio(response=response), "documents")

    result = await storage.get("parsed/key")

    assert result == b"stored bytes"
    assert response.closed
    assert response.released


@pytest.mark.asyncio
async def test_get_releases_response_when_read_fails() -> None:
    response = FakeResponse(error=RuntimeError("read failed"))
    storage = MinioObjectStorage(FakeMinio(response=response), "documents")

    with pytest.raises(RuntimeError, match="read failed"):
        await storage.get("parsed/key")

    assert response.closed
    assert response.released


@pytest.mark.asyncio
async def test_get_releases_response_when_cancelled_during_get_object() -> None:
    get_started = threading.Event()
    allow_get_to_finish = threading.Event()
    response_released = threading.Event()

    class CancellationResponse(FakeResponse):
        def release_conn(self) -> None:
            super().release_conn()
            response_released.set()

    class BlockingMinio(FakeMinio):
        def get_object(self, *args: Any, **kwargs: Any) -> FakeResponse:
            get_started.set()
            assert allow_get_to_finish.wait(timeout=5)
            return super().get_object(*args, **kwargs)

    response = CancellationResponse()
    storage = MinioObjectStorage(BlockingMinio(response=response), "documents")
    task = asyncio.create_task(storage.get("parsed/key"))
    assert await asyncio.to_thread(get_started.wait, 5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    allow_get_to_finish.set()

    assert await asyncio.to_thread(response_released.wait, 5)
    assert response.closed
    assert response.released


@pytest.mark.asyncio
async def test_sdk_errors_are_propagated() -> None:
    class FailingMinio(FakeMinio):
        def remove_object(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("delete failed")

    storage = MinioObjectStorage(FailingMinio(), "documents")

    with pytest.raises(RuntimeError, match="delete failed"):
        await storage.delete("source/key")
