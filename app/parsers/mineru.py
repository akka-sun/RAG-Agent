import httpx

from app.parsers._http import (
    extract_blocks,
    extract_version,
    json_mapping,
    raise_for_parser_status,
)
from app.parsers.types import ParsedDocument


class MinerUParser:
    name = "mineru"

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def parse_pdf(self, filename: str, content: bytes) -> ParsedDocument:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = await client.post(
                "/file_parse",
                files={"file": (filename, content, "application/pdf")},
            )
        raise_for_parser_status(self.name, response)
        payload = json_mapping(self.name, response)
        return ParsedDocument(
            parser="mineru",
            source_format="pdf",
            parser_version=extract_version(payload),
            blocks=extract_blocks(self.name, payload),
            metadata={"filename": filename},
        )
