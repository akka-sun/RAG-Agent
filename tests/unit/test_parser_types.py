from app.parsers.types import ParsedAsset, ParsedBlock, ParsedDocument


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


def test_parsed_asset_binary_is_not_serialized() -> None:
    parsed = ParsedDocument(
        parser="mineru",
        source_format="pdf",
        blocks=[ParsedBlock(text="![chart](images/chart.png)", block_index=0)],
        assets=[
            ParsedAsset(
                asset_index=0,
                source_path="images/chart.png",
                mime_type="image/png",
                content=b"png-bytes",
                object_key="documents/doc/images/0000.png",
            )
        ],
    )

    payload = parsed.model_dump()

    assert payload["assets"][0]["object_key"] == "documents/doc/images/0000.png"
    assert "content" not in payload["assets"][0]
