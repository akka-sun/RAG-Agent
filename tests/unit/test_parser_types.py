from app.parsers.types import ParsedBlock, ParsedDocument


def test_parsed_document_preserves_page_and_heading_metadata() -> None:
    parsed = ParsedDocument(
        parser="mineru",
        source_format="pdf",
        parser_version="1.0.0",
        blocks=[
            ParsedBlock(
                text="Clause 1",
                page_number=3,
                heading_path=["Terms"],
                block_index=0,
                ocr_confidence=0.98,
                coordinates=[10.0, 20.0, 300.0, 360.0],
            ),
        ],
        metadata={"filename": "terms.pdf"},
    )

    assert parsed.blocks[0].page_number == 3
    assert parsed.blocks[0].heading_path == ["Terms"]
    assert parsed.blocks[0].ocr_confidence == 0.98
    assert parsed.blocks[0].coordinates == [10.0, 20.0, 300.0, 360.0]
    assert parsed.parser_version == "1.0.0"
    assert parsed.metadata["filename"] == "terms.pdf"
