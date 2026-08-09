import uuid
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class RAGDocumentCreate(BaseModel):
    knowledge_base_id: uuid.UUID
    filename: str = Field(
        min_length=1,
        max_length=255,
    )
    content: str = Field(min_length=1)

    @field_validator("filename")
    @classmethod
    def validate_filename(
        cls,
        value: str,
    ) -> str:
        filename = value.strip()

        if Path(filename).suffix.lower() not in {
            ".md",
            ".txt",
        }:
            raise ValueError("filename must use .md or .txt")

        return filename

    @field_validator("content")
    @classmethod
    def validate_content(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")

        return value


class RAGDocumentResponse(BaseModel):
    document_id: uuid.UUID
    chunk_count: int


class RAGQueryRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    query: str = Field(min_length=1)
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
    )

    @field_validator("query")
    @classmethod
    def validate_query(
        cls,
        value: str,
    ) -> str:
        query = value.strip()

        if not query:
            raise ValueError("query must not be blank")

        return query


class RAGSourceResponse(BaseModel):
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


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[RAGSourceResponse]


class AgentQueryRequest(RAGQueryRequest):
    pass


class AgentQueryResponse(RAGQueryResponse):
    pass
