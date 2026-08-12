from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field


def _empty_citations() -> list[EvaluationCitation]:
    return []


def _empty_facts() -> list[str]:
    return []


def _empty_tags() -> list[str]:
    return []


def _empty_questions() -> list[EvaluationQuestion]:
    return []


class EvaluationCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: UUID
    chunk_id: str | None = None
    source_label: str | None = None
    quote: str | None = None
    tags: list[str] = Field(default_factory=_empty_tags)


class EvaluationQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    question: str
    expected_document_ids: list[UUID]
    expected_citations: list[EvaluationCitation] = Field(default_factory=_empty_citations)
    expected_answer_facts: list[str] = Field(default_factory=_empty_facts)
    tags: list[str] = Field(default_factory=_empty_tags)


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    knowledge_base_id: UUID | None = None
    questions: list[EvaluationQuestion] = Field(default_factory=_empty_questions)


def load_dataset(path: Path) -> EvaluationDataset:
    raw = path.read_text(encoding="utf-8")
    parsed: object = (
        yaml.safe_load(raw) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
    )
    if not isinstance(parsed, dict):
        msg = "evaluation dataset must be a JSON/YAML object"
        raise ValueError(msg)
    data = cast(dict[str, Any], parsed)
    return EvaluationDataset.model_validate(data)
