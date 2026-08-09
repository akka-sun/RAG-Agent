from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TypedDict


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


class AgentState(TypedDict, total=False):
    query: str
    knowledge_base_id: str
    normalized_query: str
    retrieval_count: int
    evidence: list[AgentEvidence]
    final_answer: str
    error: str
