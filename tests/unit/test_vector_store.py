import uuid

from app.rag.store import InMemoryVectorStore
from app.rag.types import IndexedChunk


def make_chunk(
    knowledge_base_id: uuid.UUID,
    chunk_id: str,
    vector: tuple[float, ...],
) -> IndexedChunk:
    return IndexedChunk(
        knowledge_base_id=knowledge_base_id,
        document_id=uuid.uuid4(),
        filename="notes.txt",
        chunk_id=chunk_id,
        text=chunk_id,
        start=0,
        end=len(chunk_id),
        vector=vector,
    )


def test_store_ranks_positive_scores_and_applies_top_k() -> None:
    knowledge_base_id = uuid.uuid4()
    store = InMemoryVectorStore()

    store.add(
        [
            make_chunk(
                knowledge_base_id,
                "second",
                (0.6, 0.8),
            ),
            make_chunk(
                knowledge_base_id,
                "first",
                (1.0, 0.0),
            ),
            make_chunk(
                knowledge_base_id,
                "filtered",
                (-1.0, 0.0),
            ),
        ]
    )

    results = store.search(
        knowledge_base_id,
        (1.0, 0.0),
        top_k=2,
    )

    assert [result.chunk.chunk_id for result in results] == [
        "first",
        "second",
    ]
    assert [result.score for result in results] == [
        1.0,
        0.6,
    ]


def test_store_isolates_knowledge_bases() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    store = InMemoryVectorStore()

    store.add(
        [
            make_chunk(
                first_id,
                "first",
                (1.0, 0.0),
            )
        ]
    )

    results = store.search(
        second_id,
        (1.0, 0.0),
        top_k=3,
    )

    assert results == []
