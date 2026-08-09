import uuid
from typing import Any

import pytest

from app.infrastructure.milvus_store import MilvusChunk, MilvusChunkStore, MilvusDocumentIndex
from app.rag.types import IndexedChunk

KB_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOC_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class FakeMilvusClient:
    def __init__(self) -> None:
        self.deleted_filter: str | None = None
        self.inserted_data: list[dict[str, object]] | None = None
        self.search_calls: list[dict[str, object]] = []
        self.search_results: list[list[dict[str, object]]] = [
            [
                {
                    "id": "chunk-1",
                    "distance": 0.8,
                    "entity": {
                        "chunk_id": "chunk-1",
                        "document_id": str(DOC_ID),
                        "filename": "guide.md",
                        "text": "refund policy",
                        "start": 0,
                        "end": 13,
                    },
                }
            ]
        ]

    def delete(self, collection_name: str, filter: str) -> dict[str, int]:
        del collection_name
        self.deleted_filter = filter
        return {"delete_count": 1}

    def insert(self, collection_name: str, data: list[dict[str, object]]) -> dict[str, int]:
        del collection_name
        self.inserted_data = data
        return {"insert_count": len(data)}

    def search(self, collection_name: str, **kwargs: Any) -> list[list[dict[str, object]]]:
        self.search_calls.append({"collection_name": collection_name, **kwargs})
        return self.search_results


class FakeMilvusChunkStore:
    def __init__(self) -> None:
        self.upserted_chunks: list[MilvusChunk] = []
        self.deleted_documents: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def ensure_collection(self) -> None:
        return None

    async def upsert_document_chunks(self, chunks: list[MilvusChunk]) -> None:
        self.upserted_chunks = chunks

    async def delete_document(
        self, document_id: uuid.UUID, knowledge_base_id: uuid.UUID | None = None
    ) -> None:
        assert knowledge_base_id is not None
        self.deleted_documents.append((knowledge_base_id, document_id))


def make_chunk(chunk_id: str = "chunk-1") -> MilvusChunk:
    return MilvusChunk(
        knowledge_base_id=KB_ID,
        document_id=DOC_ID,
        filename="guide.md",
        chunk_id=chunk_id,
        text="refund policy",
        start=0,
        end=13,
        vector=[0.1, 0.2, 0.3],
    )


def make_indexed_chunk(chunk_id: str = "chunk-1") -> IndexedChunk:
    return IndexedChunk(
        knowledge_base_id=KB_ID,
        document_id=DOC_ID,
        filename="guide.md",
        chunk_id=chunk_id,
        text="refund policy",
        start=0,
        end=13,
        vector=(0.1, 0.2, 0.3),
    )


@pytest.mark.asyncio
async def test_delete_document_uses_document_filter() -> None:
    fake = FakeMilvusClient()
    store = MilvusChunkStore(client=fake, collection_name="rag_chunks", embedding_dimension=3)

    await store.delete_document(DOC_ID)

    assert fake.deleted_filter == f'document_id == "{DOC_ID}"'


@pytest.mark.asyncio
async def test_delete_document_can_include_knowledge_base_filter() -> None:
    fake = FakeMilvusClient()
    store = MilvusChunkStore(client=fake, collection_name="rag_chunks", embedding_dimension=3)

    await store.delete_document(DOC_ID, knowledge_base_id=KB_ID)

    assert fake.deleted_filter == f'knowledge_base_id == "{KB_ID}" and document_id == "{DOC_ID}"'


@pytest.mark.asyncio
async def test_upsert_document_chunks_replaces_existing_document_before_insert() -> None:
    fake = FakeMilvusClient()
    store = MilvusChunkStore(client=fake, collection_name="rag_chunks", embedding_dimension=3)

    await store.upsert_document_chunks([make_chunk()])

    assert fake.deleted_filter == f'knowledge_base_id == "{KB_ID}" and document_id == "{DOC_ID}"'
    assert fake.inserted_data == [
        {
            "chunk_id": "chunk-1",
            "knowledge_base_id": str(KB_ID),
            "document_id": str(DOC_ID),
            "filename": "guide.md",
            "text": "refund policy",
            "start": 0,
            "end": 13,
            "page_number": None,
            "section": None,
            "parser_name": None,
            "block_index": None,
            "metadata": {},
            "dense_vector": [0.1, 0.2, 0.3],
        }
    ]


@pytest.mark.asyncio
async def test_search_dense_applies_knowledge_base_filter_and_maps_hits() -> None:
    fake = FakeMilvusClient()
    store = MilvusChunkStore(client=fake, collection_name="rag_chunks", embedding_dimension=3)

    results = await store.search_dense(KB_ID, [0.1, 0.2, 0.3], limit=5)

    assert fake.search_calls[0]["filter"] == f'knowledge_base_id == "{KB_ID}"'
    assert fake.search_calls[0]["anns_field"] == "dense_vector"
    assert fake.search_calls[0]["data"] == [[0.1, 0.2, 0.3]]
    assert results[0].chunk_id == "chunk-1"
    assert results[0].rank == 1
    assert results[0].score == 0.8
    assert results[0].source == "dense"


@pytest.mark.asyncio
async def test_search_sparse_uses_query_text_and_bm25_field() -> None:
    fake = FakeMilvusClient()
    store = MilvusChunkStore(client=fake, collection_name="rag_chunks", embedding_dimension=3)

    await store.search_sparse(KB_ID, "refund policy", limit=5)

    assert fake.search_calls[0]["filter"] == f'knowledge_base_id == "{KB_ID}"'
    assert fake.search_calls[0]["anns_field"] == "sparse_vector"
    assert fake.search_calls[0]["data"] == ["refund policy"]


@pytest.mark.asyncio
async def test_document_index_converts_indexed_chunks_for_milvus() -> None:
    fake = FakeMilvusChunkStore()
    index = MilvusDocumentIndex(fake)

    await index.replace_document(KB_ID, DOC_ID, [make_indexed_chunk()])

    assert len(fake.upserted_chunks) == 1
    assert fake.upserted_chunks[0].knowledge_base_id == KB_ID
    assert fake.upserted_chunks[0].document_id == DOC_ID
    assert fake.upserted_chunks[0].chunk_id == "chunk-1"
    assert list(fake.upserted_chunks[0].vector) == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_document_index_delete_uses_knowledge_base_filter() -> None:
    fake = FakeMilvusChunkStore()
    index = MilvusDocumentIndex(fake)

    await index.delete_document(KB_ID, DOC_ID)

    assert fake.deleted_documents == [(KB_ID, DOC_ID)]
