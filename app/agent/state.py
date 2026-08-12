from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypedDict


def _empty_metadata() -> dict[str, object]:
    return {}


@dataclass(frozen=True, slots=True)
class AgentEvidence:
    label: str
    document_id: uuid.UUID
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    score: float
    page_number: int | None = None
    section: str | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)


class AgentState(TypedDict, total=False):
    query: str
    knowledge_base_id: str
    normalized_query: str
    classification: str
    needs_more_evidence: bool
    retrieval_count: int
    evidence: list[AgentEvidence]
    final_answer: str
    error: str
