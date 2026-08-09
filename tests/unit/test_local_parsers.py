import pytest

from app.parsers.local import parse_markdown, parse_txt


def test_markdown_parser_extracts_heading_path() -> None:
    parsed = parse_markdown(
        "guide.md",
        b"# Setup\n\nInstall Docker.\n\n## Run\n\nStart services.",
    )

    assert parsed.parser == "local"
    assert parsed.source_format == "md"
    assert [block.text for block in parsed.blocks] == [
        "Install Docker.",
        "Start services.",
    ]
    assert parsed.blocks[0].heading_path == ["Setup"]
    assert parsed.blocks[1].heading_path == ["Setup", "Run"]


def test_txt_parser_splits_paragraph_blocks() -> None:
    parsed = parse_txt("notes.txt", b"First paragraph.\n\nSecond paragraph.")

    assert parsed.parser == "local"
    assert parsed.source_format == "txt"
    assert [block.text for block in parsed.blocks] == [
        "First paragraph.",
        "Second paragraph.",
    ]


def test_local_parser_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="empty document"):
        parse_txt("empty.txt", b" \n\n")
