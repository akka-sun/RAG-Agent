import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field


def _empty_metadata() -> dict[str, object]:
    return {}


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    text: str
    start: int
    end: int
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)


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
    page_number: int | None = None
    section: str | None = None
    parser_name: str | None = None
    block_index: int | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk: IndexedChunk
    score: float
