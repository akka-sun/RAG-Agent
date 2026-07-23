import pytest

from app.rag.chunking import chunk_text


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
