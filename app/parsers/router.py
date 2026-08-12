from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from app.core.exceptions import UnsupportedDocumentError, UnsupportedParserError
from app.parsers.local import parse_markdown, parse_txt
from app.parsers.types import ParsedDocument, ParserName, SourceFormat

PdfParserName = Literal["mineru", "paddlex"]


class PdfParserProtocol(Protocol):
    name: str

    async def parse_pdf(self, filename: str, content: bytes) -> ParsedDocument: ...


@dataclass(frozen=True, slots=True)
class ParserSelection:
    name: ParserName
    source_format: SourceFormat


class ParserRouter:
    def __init__(
        self,
        *,
        default_pdf_parser: str = "mineru",
        mineru: PdfParserProtocol | None = None,
        paddlex: PdfParserProtocol | None = None,
    ) -> None:
        if default_pdf_parser not in {"mineru", "paddlex"}:
            raise UnsupportedParserError("default PDF parser must be mineru or paddlex")
        self.default_pdf_parser: PdfParserName = cast(PdfParserName, default_pdf_parser)
        self.mineru = mineru
        self.paddlex = paddlex

    def select(self, filename: str, parser: str | None) -> ParserSelection:
        suffix = Path(filename).suffix.lower()
        requested = parser.strip().lower() if parser is not None else None

        if suffix == ".md":
            return self._select_local(requested, "md")
        if suffix == ".txt":
            return self._select_local(requested, "txt")
        if suffix == ".pdf":
            if requested is None or requested == "":
                return ParserSelection(self.default_pdf_parser, "pdf")
            if requested in {"mineru", "paddlex"}:
                return ParserSelection(cast(ParserName, requested), "pdf")
            raise UnsupportedParserError("PDF parser must be mineru or paddlex")
        raise UnsupportedDocumentError("only .md, .txt and .pdf files are supported")

    async def parse_document(
        self,
        filename: str,
        content: bytes,
        parser: str | None,
    ) -> ParsedDocument:
        selection = self.select(filename, parser)
        if selection.source_format == "md":
            return parse_markdown(filename, content)
        if selection.source_format == "txt":
            return parse_txt(filename, content)
        if selection.name == "mineru" and self.mineru is not None:
            return await self.mineru.parse_pdf(filename, content)
        if selection.name == "paddlex" and self.paddlex is not None:
            return await self.paddlex.parse_pdf(filename, content)
        raise UnsupportedParserError(f"{selection.name} parser client is not configured")

    def _select_local(self, requested: str | None, source_format: SourceFormat) -> ParserSelection:
        if requested is None or requested in {"", "local"}:
            return ParserSelection("local", source_format)
        raise UnsupportedParserError("Markdown and TXT files only support the local parser")
