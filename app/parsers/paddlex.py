import base64

import httpx

from app.parsers._http import (
    extract_blocks,
    extract_version,
    json_mapping,
    raise_for_parser_status,
)
from app.parsers.types import ParsedDocument


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
            "filename": filename,
            "fileType": "pdf",
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = await client.post(self.endpoint, json=request)
        raise_for_parser_status(self.name, response)
        payload = json_mapping(self.name, response)
        return ParsedDocument(
            parser="paddlex",
            source_format="pdf",
            parser_version=extract_version(payload),
            blocks=extract_blocks(self.name, payload),
            metadata={"filename": filename},
        )
