import pytest

from app.core.exceptions import UnsupportedDocumentError, UnsupportedParserError
from app.parsers.router import ParserRouter


def test_pdf_uses_explicit_parser() -> None:
    router = ParserRouter(default_pdf_parser="mineru")

    selection = router.select("paper.pdf", parser="paddlex")

    assert selection.name == "paddlex"
    assert selection.source_format == "pdf"


def test_pdf_uses_configured_default_parser_when_parser_is_absent() -> None:
    router = ParserRouter(default_pdf_parser="paddlex")

    selection = router.select("paper.pdf", parser=None)

    assert selection.name == "paddlex"


def test_markdown_rejects_external_parser() -> None:
    router = ParserRouter(default_pdf_parser="mineru")

    with pytest.raises(UnsupportedParserError):
        router.select("readme.md", parser="mineru")


def test_text_uses_local_parser() -> None:
    router = ParserRouter(default_pdf_parser="mineru")

    selection = router.select("notes.txt", parser="local")

    assert selection.name == "local"
    assert selection.source_format == "txt"


def test_unsupported_file_suffix_is_rejected() -> None:
    router = ParserRouter(default_pdf_parser="mineru")

    with pytest.raises(UnsupportedDocumentError):
        router.select("slides.pptx", parser=None)
