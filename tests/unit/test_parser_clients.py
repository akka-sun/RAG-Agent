import httpx
import pytest

from app.parsers.mineru import MinerUParser
from app.parsers.paddlex import PaddleXParser
from app.parsers.types import ParserServiceError


@pytest.mark.unit
async def test_mineru_parser_maps_blocks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/file_parse"
        return httpx.Response(
            200,
            json={
                "blocks": [
                    {
                        "text": "PDF text",
                        "page": 1,
                        "type": "paragraph",
                        "bbox": [1, 2, 3, 4],
                    }
                ],
                "version": "mineru-test",
            },
        )

    parser = MinerUParser(
        base_url="http://mineru.test",
        transport=httpx.MockTransport(handler),
    )

    parsed = await parser.parse_pdf("doc.pdf", b"%PDF")

    assert parsed.parser == "mineru"
    assert parsed.parser_version == "mineru-test"
    assert parsed.blocks[0].text == "PDF text"
    assert parsed.blocks[0].page_number == 1
    assert parsed.blocks[0].coordinates == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.unit
async def test_paddlex_parser_maps_layout_parsing_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/layout-parsing"
        return httpx.Response(
            200,
            json={
                "result": {
                    "layoutParsingResults": [
                        {
                            "prunedResult": [
                                {
                                    "text": "OCR text",
                                    "page_number": 2,
                                    "type": "text",
                                    "confidence": 0.91,
                                }
                            ]
                        }
                    ]
                },
                "version": "paddlex-test",
            },
        )

    parser = PaddleXParser(
        base_url="http://paddlex.test",
        transport=httpx.MockTransport(handler),
    )

    parsed = await parser.parse_pdf("scan.pdf", b"%PDF")

    assert parsed.parser == "paddlex"
    assert parsed.parser_version == "paddlex-test"
    assert parsed.blocks[0].text == "OCR text"
    assert parsed.blocks[0].page_number == 2
    assert parsed.blocks[0].ocr_confidence == 0.91


@pytest.mark.unit
async def test_parser_client_raises_service_error_for_http_failure() -> None:
    parser = MinerUParser(
        base_url="http://mineru.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(503, text="busy")),
    )

    with pytest.raises(ParserServiceError) as exc_info:
        await parser.parse_pdf("doc.pdf", b"%PDF")

    assert exc_info.value.parser == "mineru"
    assert exc_info.value.status_code == 503
    assert "busy" in str(exc_info.value)
