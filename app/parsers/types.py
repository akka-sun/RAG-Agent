from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ParserName = Literal["local", "mineru", "paddlex"]
SourceFormat = Literal["md", "txt", "pdf"]


class ParsedBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    block_index: int
    block_type: str = "paragraph"
    page_number: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    ocr_confidence: float | None = None
    coordinates: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    parser: ParserName
    source_format: SourceFormat
    blocks: list[ParsedBlock]
    parser_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
