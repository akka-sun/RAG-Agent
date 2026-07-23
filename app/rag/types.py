import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk: IndexedChunk
    score: float
