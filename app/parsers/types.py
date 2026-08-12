from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ParserName = Literal["local", "mineru", "paddlex"]
SourceFormat = Literal["md", "txt", "pdf"]


class ParserServiceError(RuntimeError):
    def __init__(self, parser: str, status_code: int | None, message: str) -> None:
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(f"{parser} parser failed{status}: {message}")
        self.parser = parser
        self.status_code = status_code
        self.message = message


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


class ParsedAsset(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_index: int = Field(ge=0)
    source_path: str
    mime_type: str
    content: bytes = Field(default=b"", exclude=True, repr=False)
    object_key: str | None = None
    url: str | None = None
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _empty_assets() -> list[ParsedAsset]:
    return []


class ParsedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    parser: ParserName
    source_format: SourceFormat
    blocks: list[ParsedBlock]
    markdown: str | None = None
    assets: list[ParsedAsset] = Field(default_factory=_empty_assets)
    parser_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
