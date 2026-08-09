from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from pymilvus import DataType, Function, FunctionType, MilvusClient

from app.rag.hybrid import RetrievedChunk

DENSE_VECTOR_FIELD = "dense_vector"
SPARSE_VECTOR_FIELD = "sparse_vector"
TEXT_FIELD = "text"
OUTPUT_FIELDS = [
    "chunk_id",
    "knowledge_base_id",
    "document_id",
    "filename",
    TEXT_FIELD,
    "start",
    "end",
]


@dataclass(frozen=True, slots=True)
class MilvusChunk:
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    vector: Sequence[float]


class MilvusChunkStore:
    def __init__(
        self,
        *,
        collection_name: str,
        embedding_dimension: int,
        uri: str = "http://milvus-standalone:19530",
        token: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._collection_name = collection_name
        self._embedding_dimension = embedding_dimension
        self._client = client or MilvusClient(uri=uri, token=token)

    async def ensure_collection(self) -> None:
        await asyncio.to_thread(self._ensure_collection)

    async def upsert_document_chunks(self, chunks: Sequence[MilvusChunk]) -> None:
        if not chunks:
            return
        await asyncio.to_thread(self._upsert_document_chunks, list(chunks))

    async def search_dense(
        self, knowledge_base_id: uuid.UUID, query_vector: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        hits = await asyncio.to_thread(
            self._client.search,
            collection_name=self._collection_name,
            data=[list(query_vector)],
            anns_field=DENSE_VECTOR_FIELD,
            filter=_knowledge_base_filter(knowledge_base_id),
            limit=limit,
            output_fields=OUTPUT_FIELDS,
            search_params={"metric_type": "COSINE", "params": {}},
        )
        return _map_hits(cast(list[list[dict[str, object]]], hits), source="dense")

    async def search_sparse(
        self, knowledge_base_id: uuid.UUID, query_text: str, limit: int
    ) -> list[RetrievedChunk]:
        hits = await asyncio.to_thread(
            self._client.search,
            collection_name=self._collection_name,
            data=[query_text],
            anns_field=SPARSE_VECTOR_FIELD,
            filter=_knowledge_base_filter(knowledge_base_id),
            limit=limit,
            output_fields=OUTPUT_FIELDS,
            search_params={"params": {}},
        )
        return _map_hits(cast(list[list[dict[str, object]]], hits), source="sparse")

    async def delete_document(
        self,
        document_id: uuid.UUID,
        knowledge_base_id: uuid.UUID | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._client.delete,
            collection_name=self._collection_name,
            filter=_document_filter(document_id, knowledge_base_id),
        )

    def _ensure_collection(self) -> None:
        if self._client.has_collection(self._collection_name):
            self._client.load_collection(self._collection_name)
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=256)
        schema.add_field("knowledge_base_id", DataType.VARCHAR, max_length=36)
        schema.add_field("document_id", DataType.VARCHAR, max_length=36)
        schema.add_field("filename", DataType.VARCHAR, max_length=1024)
        schema.add_field(TEXT_FIELD, DataType.VARCHAR, max_length=65535, enable_analyzer=True)
        schema.add_field("start", DataType.INT64)
        schema.add_field("end", DataType.INT64)
        schema.add_field(DENSE_VECTOR_FIELD, DataType.FLOAT_VECTOR, dim=self._embedding_dimension)
        schema.add_field(SPARSE_VECTOR_FIELD, DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="text_bm25",
                function_type=FunctionType.BM25,
                input_field_names=[TEXT_FIELD],
                output_field_names=[SPARSE_VECTOR_FIELD],
            )
        )

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name=DENSE_VECTOR_FIELD,
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        index_params.add_index(
            field_name=SPARSE_VECTOR_FIELD,
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
            params={"inverted_index_algo": "DAAT_MAXSCORE"},
        )

        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
        )
        self._client.load_collection(self._collection_name)

    def _upsert_document_chunks(self, chunks: list[MilvusChunk]) -> None:
        first = chunks[0]
        if any(
            chunk.knowledge_base_id != first.knowledge_base_id
            or chunk.document_id != first.document_id
            for chunk in chunks
        ):
            msg = "all Milvus chunks in one upsert must belong to the same document"
            raise ValueError(msg)

        self._client.delete(
            collection_name=self._collection_name,
            filter=_document_filter(first.document_id, first.knowledge_base_id),
        )
        self._client.insert(
            collection_name=self._collection_name,
            data=[_serialize_chunk(chunk) for chunk in chunks],
        )


def _serialize_chunk(chunk: MilvusChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "knowledge_base_id": str(chunk.knowledge_base_id),
        "document_id": str(chunk.document_id),
        "filename": chunk.filename,
        TEXT_FIELD: chunk.text,
        "start": chunk.start,
        "end": chunk.end,
        DENSE_VECTOR_FIELD: list(chunk.vector),
    }


def _knowledge_base_filter(knowledge_base_id: uuid.UUID) -> str:
    return f'knowledge_base_id == "{_escape_filter_value(str(knowledge_base_id))}"'


def _document_filter(
    document_id: uuid.UUID,
    knowledge_base_id: uuid.UUID | None = None,
) -> str:
    document_clause = f'document_id == "{_escape_filter_value(str(document_id))}"'
    if knowledge_base_id is None:
        return document_clause
    return f"{_knowledge_base_filter(knowledge_base_id)} and {document_clause}"


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _map_hits(results: list[list[dict[str, object]]], *, source: str) -> list[RetrievedChunk]:
    hits = results[0] if results else []
    return [_map_hit(hit, rank=rank, source=source) for rank, hit in enumerate(hits, start=1)]


def _map_hit(hit: Mapping[str, object], *, rank: int, source: str) -> RetrievedChunk:
    entity = _entity_from_hit(hit)
    return RetrievedChunk(
        chunk_id=_string_field(entity, "chunk_id", fallback=hit.get("id")),
        document_id=_string_field(entity, "document_id"),
        text=_string_field(entity, TEXT_FIELD),
        rank=rank,
        score=_float_field(hit, "distance"),
        source=source,
        metadata={
            "knowledge_base_id": _string_field(entity, "knowledge_base_id"),
            "filename": _string_field(entity, "filename"),
            "start": _int_field(entity, "start"),
            "end": _int_field(entity, "end"),
        },
    )


def _entity_from_hit(hit: Mapping[str, object]) -> Mapping[str, object]:
    entity = hit.get("entity", {})
    if isinstance(entity, Mapping):
        return cast(Mapping[str, object], entity)
    return {}


def _string_field(
    data: Mapping[str, object],
    key: str,
    *,
    fallback: object = "",
) -> str:
    value = data.get(key, fallback)
    return "" if value is None else str(value)


def _int_field(data: Mapping[str, object], key: str) -> int:
    value = data.get(key, 0)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        return int(value)
    return 0


def _float_field(data: Mapping[str, object], key: str) -> float:
    value = data.get(key, 0.0)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    return 0.0
