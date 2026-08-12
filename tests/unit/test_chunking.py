import pytest

from app.parsers.types import ParsedBlock, ParsedDocument
from app.rag.chunking import chunk_parsed_document, chunk_text


def test_chunk_text_uses_overlapping_character_windows() -> None:
    chunks = chunk_text(
        "abcdefghij",
        chunk_size=4,
        overlap=1,
    )

    assert [(chunk.text, chunk.start, chunk.end) for chunk in chunks] == [
        ("abcd", 0, 4),
        ("defg", 3, 7),
        ("ghij", 6, 10),
    ]
    assert [chunk.index for chunk in chunks] == [0, 1, 2]


def test_chunk_text_normalizes_line_endings_and_empty_input() -> None:
    chunks = chunk_text(
        "  first\r\nsecond  ",
        chunk_size=20,
        overlap=2,
    )

    assert [chunk.text for chunk in chunks] == ["first\nsecond"]
    assert chunk_text("  \r\n  ") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [
        (0, 0),
        (4, -1),
        (4, 4),
        (4, 5),
    ],
)
def test_chunk_text_rejects_invalid_window_configuration(
    chunk_size: int,
    overlap: int,
) -> None:
    with pytest.raises(ValueError):
        chunk_text(
            "content",
            chunk_size=chunk_size,
            overlap=overlap,
        )


def test_chunk_parsed_document_preserves_page_metadata() -> None:
    parsed = ParsedDocument(
        parser="mineru",
        source_format="pdf",
        parser_version="mineru-1",
        blocks=[
            ParsedBlock(
                text="A long paragraph about retention.",
                page_number=2,
                heading_path=["Policy", "Retention"],
                block_index=7,
                block_type="text",
                ocr_confidence=0.97,
                coordinates=[1.0, 2.0, 3.0, 4.0],
            )
        ],
    )

    chunks = chunk_parsed_document(parsed)

    assert chunks[0].metadata["page_number"] == 2
    assert chunks[0].metadata["parser"] == "mineru"
    assert chunks[0].metadata["section"] == "Policy > Retention"
    assert chunks[0].metadata["block_index"] == 7
    assert chunks[0].metadata["ocr_confidence"] == 0.97
