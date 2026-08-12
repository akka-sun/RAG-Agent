import base64
import binascii
from collections.abc import Mapping
from typing import Any, cast

import httpx

from app.parsers._http import (
    extract_blocks,
    extract_version,
    json_mapping,
    raise_for_parser_status,
)
from app.parsers.assets import build_markdown_document, infer_image_mime_type
from app.parsers.types import ParsedAsset, ParsedDocument, ParserServiceError


class PaddleXParser:
    name = "paddlex"

    def __init__(
        self,
        *,
        base_url: str,
        endpoint: str = "/layout-parsing",
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.timeout = timeout
        self.transport = transport

    async def parse_pdf(self, filename: str, content: bytes) -> ParsedDocument:
        request = {
            "file": base64.b64encode(content).decode("ascii"),
            "fileType": 0,
            "useTableRecognition": True,
            "useFormulaRecognition": True,
            "useSealRecognition": False,
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = await client.post(self.endpoint, json=request)
            raise_for_parser_status(self.name, response)
            payload = json_mapping(self.name, response)
            _raise_for_payload_error(payload)
            markdown_pages = _markdown_pages(payload)
            if markdown_pages:
                assets: list[ParsedAsset] = []
                markdown_parts: list[str] = []
                for page_number, text, images in markdown_pages:
                    markdown_parts.append(text.strip())
                    for source_path, source_url in images.items():
                        image, declared_mime = await _download_image(client, source_url)
                        assets.append(
                            ParsedAsset(
                                asset_index=len(assets),
                                source_path=source_path,
                                mime_type=infer_image_mime_type(
                                    source_path,
                                    image,
                                    declared_mime,
                                ),
                                content=image,
                                page_number=page_number,
                                metadata={"source_url": source_url},
                            )
                        )
                return build_markdown_document(
                    parser="paddlex",
                    filename=filename,
                    markdown="\n\n".join(markdown_parts),
                    assets=assets,
                    parser_version=extract_version(payload),
                    metadata={"page_count": len(markdown_pages)},
                )
        return ParsedDocument(
            parser="paddlex",
            source_format="pdf",
            parser_version=extract_version(payload),
            blocks=extract_blocks(self.name, payload),
            metadata={"filename": filename},
        )


def _raise_for_payload_error(payload: Mapping[str, Any]) -> None:
    error_code = payload.get("errorCode")
    if isinstance(error_code, int) and error_code != 0:
        message = payload.get("errorMsg")
        raise ParserServiceError("paddlex", None, str(message or f"errorCode={error_code}"))


def _markdown_pages(
    payload: Mapping[str, Any],
) -> list[tuple[int, str, dict[str, str]]]:
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return []
    layout_results = cast(Mapping[str, Any], result).get("layoutParsingResults")
    if not isinstance(layout_results, list):
        return []

    pages: list[tuple[int, str, dict[str, str]]] = []
    for index, raw_item in enumerate(cast(list[object], layout_results), start=1):
        if not isinstance(raw_item, Mapping):
            continue
        item = cast(Mapping[str, Any], raw_item)
        markdown = item.get("markdown")
        if not isinstance(markdown, Mapping):
            continue
        markdown_mapping = cast(Mapping[str, Any], markdown)
        text = markdown_mapping.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        page_number_value = _page_number(item)
        page_number = index if page_number_value is None else page_number_value
        images = markdown_mapping.get("images")
        image_urls: dict[str, str] = {}
        if isinstance(images, Mapping):
            for raw_path, raw_url in cast(Mapping[object, object], images).items():
                if isinstance(raw_path, str) and raw_path and isinstance(raw_url, str) and raw_url:
                    image_urls[raw_path] = raw_url
        pages.append((page_number, text, image_urls))
    return pages


async def _download_image(client: httpx.AsyncClient, source: str) -> tuple[bytes, str | None]:
    if source.startswith("data:"):
        header, separator, encoded = source.partition(",")
        if not separator or ";base64" not in header:
            raise ParserServiceError("paddlex", None, "unsupported image data URI")
        try:
            return base64.b64decode(encoded, validate=True), header[5:].split(";", maxsplit=1)[0]
        except binascii.Error as exc:
            raise ParserServiceError("paddlex", None, "invalid image data URI") from exc

    response = await client.get(source)
    raise_for_parser_status("paddlex image", response)
    return response.content, response.headers.get("content-type")


def _page_number(item: Mapping[str, Any]) -> int | None:
    for key in ("page", "page_number", "pageNo", "page_no"):
        value = item.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.isdecimal():
            return int(value)
    return None
