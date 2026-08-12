import zipfile
from io import BytesIO

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
        assert b'name="files"' in request.content
        assert b'name="response_format_zip"' in request.content
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
async def test_mineru_parser_reads_markdown_and_images_from_zip() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "result/full.md",
            "# Report\n\nRevenue chart\n\n![chart](images/figures/chart.png)",
        )
        archive.writestr("result/images/figures/chart.png", b"\x89PNG\r\n\x1a\nimage")

    parser = MinerUParser(
        base_url="http://mineru.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=buffer.getvalue(),
                headers={"content-type": "application/zip", "x-parser-version": "mineru-2"},
            )
        ),
    )

    parsed = await parser.parse_pdf("report.pdf", b"%PDF")

    assert parsed.markdown == "# Report\n\nRevenue chart\n\n![chart](images/figures/chart.png)"
    assert parsed.blocks[0].heading_path == ["Report"]
    assert parsed.assets[0].source_path == "images/figures/chart.png"
    assert parsed.assets[0].mime_type == "image/png"
    assert parsed.assets[0].content.startswith(b"\x89PNG")
    assert "content" not in parsed.model_dump()["assets"][0]


@pytest.mark.unit
async def test_mineru_cloud_parser_uploads_polls_and_reads_zip() -> None:
    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("result/full.md", "# Cloud result\n\nChart value: 42")

    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/api/v4/file-urls/batch":
            assert request.headers["Authorization"] == "Bearer token-test"
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.test/doc.pdf"],
                    },
                },
            )
        if request.method == "PUT" and request.url.host == "upload.test":
            assert request.content == b"%PDF cloud"
            return httpx.Response(200)
        if request.method == "GET" and request.url.path.endswith("/extract-results/batch/batch-1"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "extract_result": [
                            {
                                "file_name": "doc.pdf",
                                "state": "done",
                                "full_zip_url": "https://download.test/result.zip",
                            }
                        ],
                    },
                },
            )
        if request.method == "GET" and request.url.host == "download.test":
            return httpx.Response(
                200,
                content=archive_buffer.getvalue(),
                headers={"content-type": "application/zip"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    parser = MinerUParser(
        base_url="https://mineru.test/api/v4",
        api_key="token-test",
        model_version="vlm",
        poll_interval=0,
        transport=httpx.MockTransport(handler),
    )

    parsed = await parser.parse_pdf("doc.pdf", b"%PDF cloud")

    assert parsed.markdown == "# Cloud result\n\nChart value: 42"
    assert parsed.parser_version == "cloud-vlm"
    assert requests == [
        ("POST", "/api/v4/file-urls/batch"),
        ("PUT", "/doc.pdf"),
        ("GET", "/api/v4/extract-results/batch/batch-1"),
        ("GET", "/result.zip"),
    ]


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
async def test_paddlex_parser_reads_markdown_images() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/assets/chart.jpg":
            return httpx.Response(
                200,
                content=b"\xff\xd8\xffimage",
                headers={"content-type": "image/jpeg"},
            )
        assert request.url.path == "/layout-parsing"
        return httpx.Response(
            200,
            json={
                "errorCode": 0,
                "version": "paddlex-markdown",
                "result": {
                    "layoutParsingResults": [
                        {
                            "pageNo": 3,
                            "markdown": {
                                "text": "## Results\n\n![chart](images/chart.jpg)",
                                "images": {
                                    "images/chart.jpg": "http://paddlex.test/assets/chart.jpg"
                                },
                            },
                        }
                    ]
                },
            },
        )

    parser = PaddleXParser(
        base_url="http://paddlex.test",
        transport=httpx.MockTransport(handler),
    )

    parsed = await parser.parse_pdf("report.pdf", b"%PDF")

    assert parsed.markdown == "## Results\n\n![chart](images/chart.jpg)"
    assert parsed.assets[0].page_number == 3
    assert parsed.assets[0].mime_type == "image/jpeg"
    assert parsed.assets[0].metadata["source_url"] == "http://paddlex.test/assets/chart.jpg"


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
