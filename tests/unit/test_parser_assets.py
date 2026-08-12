import json

from app.parsers.assets import (
    asset_keys_from_parsed,
    replace_markdown_image_links,
    rewrite_document_asset_urls,
    stored_asset_from_parsed,
)
from app.parsers.types import ParsedAsset, ParsedBlock, ParsedDocument


def test_rewrite_document_asset_urls_updates_markdown_and_blocks() -> None:
    parsed = ParsedDocument(
        parser="mineru",
        source_format="pdf",
        markdown="![chart](images/chart.png)",
        blocks=[
            ParsedBlock(
                text="See ![chart](./images/chart.png)",
                block_index=0,
            )
        ],
        assets=[
            ParsedAsset(
                asset_index=0,
                source_path="images/chart.png",
                mime_type="image/png",
                content=b"png",
            )
        ],
    )
    stored = parsed.assets[0].model_copy(
        update={
            "content": b"",
            "object_key": "documents/doc/images/0000.png",
            "url": "/api/v1/documents/doc/images/0",
        }
    )

    rewritten = rewrite_document_asset_urls(parsed, [stored])

    assert rewritten.markdown == "![chart](/api/v1/documents/doc/images/0)"
    assert rewritten.blocks[0].text == "See ![chart](/api/v1/documents/doc/images/0)"
    assert rewritten.assets[0].object_key == "documents/doc/images/0000.png"


def test_replace_markdown_image_links_matches_yuxi_filename_fallback() -> None:
    markdown = "![figure](nested/path/chart.png)"

    rewritten = replace_markdown_image_links(
        markdown,
        [("images/chart.png", "https://objects.example/chart.png")],
    )

    assert rewritten == "![figure](https://objects.example/chart.png)"


def test_manifest_helpers_only_return_persisted_assets() -> None:
    content = json.dumps(
        {
            "assets": [
                {
                    "asset_index": 0,
                    "mime_type": "image/png",
                    "object_key": "images/0000.png",
                },
                {
                    "asset_index": 1,
                    "mime_type": "image/jpeg",
                    "object_key": "images/0001.jpg",
                },
            ]
        }
    ).encode()

    assert asset_keys_from_parsed(content) == ["images/0000.png", "images/0001.jpg"]
    assert stored_asset_from_parsed(content, 1) == ("images/0001.jpg", "image/jpeg")
    assert stored_asset_from_parsed(content, 2) is None
