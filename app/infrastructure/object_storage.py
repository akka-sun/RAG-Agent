from __future__ import annotations

import asyncio
import io
from typing import BinaryIO, Protocol
from uuid import UUID


class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class _ObjectResponse(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...

    def release_conn(self) -> None: ...


class _MinioClient(Protocol):
    def bucket_exists(self, bucket_name: str, /) -> bool: ...

    def make_bucket(self, bucket_name: str, /) -> object: ...

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BinaryIO,
        /,
        *,
        length: int,
        content_type: str,
    ) -> object: ...

    def get_object(self, bucket_name: str, object_name: str, /) -> _ObjectResponse: ...

    def remove_object(self, bucket_name: str, object_name: str, /) -> object: ...


def _document_prefix(knowledge_base_id: UUID, document_id: UUID) -> str:
    return f"knowledge-bases/{knowledge_base_id}/documents/{document_id}"


def source_key(knowledge_base_id: UUID, document_id: UUID, filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    if basename in {"", ".", ".."}:
        raise ValueError("filename must contain a basename")
    return f"{_document_prefix(knowledge_base_id, document_id)}/source/{basename}"


def parsed_key(knowledge_base_id: UUID, document_id: UUID) -> str:
    return f"{_document_prefix(knowledge_base_id, document_id)}/parsed.json"


class MinioObjectStorage:
    def __init__(self, client: _MinioClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket
        self._bucket_ready = False
        self._bucket_lock = asyncio.Lock()

    async def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return

        async with self._bucket_lock:
            if self._bucket_ready:
                return
            if not await asyncio.to_thread(self._client.bucket_exists, self._bucket):
                try:
                    await asyncio.to_thread(self._client.make_bucket, self._bucket)
                except Exception:
                    # Another process may have created the bucket after our existence check.
                    if not await asyncio.to_thread(self._client.bucket_exists, self._bucket):
                        raise
            self._bucket_ready = True

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await self._ensure_bucket()
        stream = io.BytesIO(data)
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            key,
            stream,
            length=len(data),
            content_type=content_type,
        )

    async def get(self, key: str) -> bytes:
        await self._ensure_bucket()
        response = await asyncio.to_thread(self._client.get_object, self._bucket, key)
        return await asyncio.to_thread(self._read_and_release, response)

    async def delete(self, key: str) -> None:
        await self._ensure_bucket()
        await asyncio.to_thread(self._client.remove_object, self._bucket, key)

    @staticmethod
    def _read_and_release(response: _ObjectResponse) -> bytes:
        try:
            return response.read()
        finally:
            try:
                response.close()
            finally:
                response.release_conn()
