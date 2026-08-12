import os

import httpx
import pytest

from app.config import Settings
from app.parsers.mineru import MinerUParser
from app.parsers.paddlex import PaddleXParser

_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
    b"/Contents 4 0 R >> endobj\n"
    b"4 0 obj << /Length 44 >> stream\nBT /F1 12 Tf 10 100 Td (hello) Tj ET\nendstream endobj\n"
    b"xref\n0 5\n0000000000 65535 f \ntrailer << /Root 1 0 R >>\n%%EOF\n"
)


def _external_tests_enabled() -> bool:
    value = os.getenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", "")
    return value.lower() in {"1", "true", "yes", "on"}


async def _service_is_running(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{base_url.rstrip('/')}/health")
    except httpx.HTTPError:
        return False
    return 200 <= response.status_code < 500


@pytest.mark.integration
@pytest.mark.external
async def test_mineru_parser_calls_real_service() -> None:
    if not _external_tests_enabled():
        pytest.skip("external parser tests are disabled")
    settings = Settings()
    if not settings.mineru_api_key and not await _service_is_running(settings.mineru_base_url):
        pytest.skip("MinerU parser service is not running")

    parsed = await MinerUParser(
        base_url=settings.mineru_base_url,
        api_key=settings.mineru_api_key,
        model_version=settings.mineru_model_version,
    ).parse_pdf(
        "minimal.pdf",
        _MINIMAL_PDF,
    )

    assert parsed.parser == "mineru"
    assert parsed.blocks


@pytest.mark.integration
@pytest.mark.external
async def test_paddlex_parser_calls_real_service() -> None:
    if not _external_tests_enabled():
        pytest.skip("external parser tests are disabled")
    settings = Settings()
    if not await _service_is_running(settings.paddlex_base_url):
        pytest.skip("PaddleX parser service is not running")

    parsed = await PaddleXParser(base_url=settings.paddlex_base_url).parse_pdf(
        "minimal.pdf",
        _MINIMAL_PDF,
    )

    assert parsed.parser == "paddlex"
    assert parsed.blocks
