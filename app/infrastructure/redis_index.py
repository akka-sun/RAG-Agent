from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any, TypedDict, cast
from uuid import UUID

from app.rag.types import IndexedChunk


class _SerializedChunk(TypedDict):
    knowledge_base_id: str
    document_id: str
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    vector: list[float]


def _key(knowledge_base_id: UUID, document_id: UUID) -> str:
    return f"rag:index:{knowledge_base_id}:{document_id}"


def _encode(chunks: list[IndexedChunk]) -> str:
    def convert(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, tuple):
            return list(cast(tuple[object, ...], value))
        return value

    return json.dumps([asdict(chunk) for chunk in chunks], default=convert)


def _decode(raw: str | bytes) -> list[IndexedChunk]:
    data = cast(list[_SerializedChunk], json.loads(raw.decode() if isinstance(raw, bytes) else raw))
    return [_decode_chunk(item) for item in data]


def _decode_chunk(item: _SerializedChunk) -> IndexedChunk:
    vector: tuple[float, ...] = tuple(item["vector"])
    return IndexedChunk(
        knowledge_base_id=UUID(item["knowledge_base_id"]),
        document_id=UUID(item["document_id"]),
        filename=item["filename"],
        chunk_id=item["chunk_id"],
        text=item["text"],
        start=item["start"],
        end=item["end"],
        vector=vector,
    )


class RedisDocumentIndex:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def replace_document(
        self, knowledge_base_id: UUID, document_id: UUID, chunks: list[IndexedChunk]
    ) -> None:
        await asyncio.to_thread(
            self._client.set, _key(knowledge_base_id, document_id), _encode(chunks)
        )

    async def get_document(self, knowledge_base_id: UUID, document_id: UUID) -> list[IndexedChunk]:
        raw = await asyncio.to_thread(self._client.get, _key(knowledge_base_id, document_id))
        return [] if raw is None else _decode(raw)

    async def delete_document(self, knowledge_base_id: UUID, document_id: UUID) -> None:
        await asyncio.to_thread(self._client.delete, _key(knowledge_base_id, document_id))
