import asyncio
import uuid

import pytest
from pymilvus import MilvusClient

from app.infrastructure.milvus_store import MilvusChunk, MilvusChunkStore


def make_chunk(
    *,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_id: str,
    text: str,
    vector: list[float],
) -> MilvusChunk:
    return MilvusChunk(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        filename="policy.md",
        chunk_id=chunk_id,
        text=text,
        start=0,
        end=len(text),
        vector=vector,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_milvus_store_isolates_knowledge_bases() -> None:
    collection_name = f"rag_chunks_test_{uuid.uuid4().hex[:12]}"
    client = MilvusClient(uri="http://milvus-standalone:19530")
    store = MilvusChunkStore(
        client=client,
        collection_name=collection_name,
        embedding_dimension=3,
    )
    first_kb = uuid.uuid4()
    second_kb = uuid.uuid4()
    first_document = uuid.uuid4()
    second_document = uuid.uuid4()

    try:
        await store.ensure_collection()
        await store.upsert_document_chunks(
            [
                make_chunk(
                    knowledge_base_id=first_kb,
                    document_id=first_document,
                    chunk_id="first-refund",
                    text="refund policy allows returns within thirty days",
                    vector=[1.0, 0.0, 0.0],
                )
            ]
        )
        await store.upsert_document_chunks(
            [
                make_chunk(
                    knowledge_base_id=second_kb,
                    document_id=second_document,
                    chunk_id="second-refund",
                    text="refund policy has a different knowledge base answer",
                    vector=[1.0, 0.0, 0.0],
                )
            ]
        )
        await asyncio.to_thread(client.flush, collection_name)

        dense_results = await store.search_dense(first_kb, [1.0, 0.0, 0.0], limit=10)
        sparse_results = await store.search_sparse(first_kb, "refund policy", limit=10)

        assert {result.document_id for result in dense_results} == {str(first_document)}
        assert {result.document_id for result in sparse_results} == {str(first_document)}
    finally:
        if client.has_collection(collection_name):
            await asyncio.to_thread(client.drop_collection, collection_name)
