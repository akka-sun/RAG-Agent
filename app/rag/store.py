import uuid

from app.rag.types import IndexedChunk, SearchResult


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: dict[
            uuid.UUID,
            list[IndexedChunk],
        ] = {}

    def add(
        self,
        chunks: list[IndexedChunk],
    ) -> None:
        for chunk in chunks:
            self._items.setdefault(
                chunk.knowledge_base_id,
                [],
            ).append(chunk)

    def search(
        self,
        knowledge_base_id: uuid.UUID,
        query_vector: tuple[float, ...],
        top_k: int,
    ) -> list[SearchResult]:
        results = [
            SearchResult(
                chunk=chunk,
                score=sum(
                    query_value * chunk_value
                    for query_value, chunk_value in zip(
                        query_vector,
                        chunk.vector,
                        strict=True,
                    )
                ),
            )
            for chunk in self._items.get(
                knowledge_base_id,
                [],
            )
        ]

        positive_results = [result for result in results if result.score > 0.0]

        positive_results.sort(
            key=lambda result: (
                -result.score,
                result.chunk.chunk_id,
            )
        )

        return positive_results[:top_k]
