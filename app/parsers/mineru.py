import asyncio
import time
import zipfile
from collections.abc import Mapping
from io import BytesIO
from pathlib import PurePosixPath
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

_MAX_ARCHIVE_FILES = 1000
_MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
_MAX_IMAGE_BYTES = 50 * 1024 * 1024
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


class MinerUParser:
    name = "mineru"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model_version: str = "vlm",
        timeout: float = 120.0,
        poll_interval: float = 2.0,
        max_poll_seconds: float = 600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_version = model_version
        self.timeout = timeout
        self.poll_interval = max(poll_interval, 0.0)
        self.max_poll_seconds = max(max_poll_seconds, 1.0)
        self.transport = transport

    async def parse_pdf(self, filename: str, content: bytes) -> ParsedDocument:
        if self.api_key:
            return await self._parse_cloud_pdf(filename, content)
        return await self._parse_local_pdf(filename, content)

    async def _parse_local_pdf(self, filename: str, content: bytes) -> ParsedDocument:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = await client.post(
                "/file_parse",
                files={"files": (filename, content, "application/octet-stream")},
                data={
                    "lang_list": "ch",
                    "backend": "hybrid-auto-engine",
                    "parse_method": "auto",
                    "formula_enable": "true",
                    "table_enable": "true",
                    "image_analysis": "true",
                    "start_page_id": "0",
                    "end_page_id": "99999",
                    "return_md": "true",
                    "response_format_zip": "true",
                    "return_images": "true",
                },
            )
        raise_for_parser_status(self.name, response)
        if _is_zip_response(response):
            return _parse_archive(
                filename,
                response.content,
                parser_version=response.headers.get("x-parser-version"),
            )
        payload = json_mapping(self.name, response)
        return ParsedDocument(
            parser="mineru",
            source_format="pdf",
            parser_version=extract_version(payload),
            blocks=extract_blocks(self.name, payload),
            metadata={"filename": filename},
        )

    async def _parse_cloud_pdf(self, filename: str, content: bytes) -> ParsedDocument:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            create_response = await client.post(
                "/file-urls/batch",
                headers=headers,
                json={
                    "files": [{"name": filename}],
                    "model_version": self.model_version,
                    "enable_formula": True,
                    "enable_table": True,
                    "language": "ch",
                },
            )
            create_data = _cloud_data(create_response, "create upload task")
            batch_id = _required_cloud_string(create_data, "batch_id")
            upload_url = _first_cloud_url(create_data.get("file_urls"))

            upload_response = await client.put(upload_url, content=content)
            raise_for_parser_status("mineru cloud upload", upload_response)

            deadline = time.monotonic() + self.max_poll_seconds
            while True:
                result_response = await client.get(
                    f"/extract-results/batch/{batch_id}",
                    headers=headers,
                )
                result_data = _cloud_data(result_response, "poll parse task")
                result = _cloud_result_for_file(result_data, filename)
                state = str(result.get("state", "")).lower()
                if state == "done":
                    archive_url = _required_cloud_string(result, "full_zip_url")
                    archive_response = await client.get(archive_url)
                    raise_for_parser_status("mineru cloud result", archive_response)
                    return _parse_archive(
                        filename,
                        archive_response.content,
                        parser_version=f"cloud-{self.model_version}",
                    )
                if state == "failed":
                    message = result.get("err_msg") or "cloud parse task failed"
                    raise ParserServiceError(self.name, None, str(message))
                if time.monotonic() >= deadline:
                    raise ParserServiceError(
                        self.name,
                        None,
                        f"cloud parse task timed out after {self.max_poll_seconds:.0f}s",
                    )
                await asyncio.sleep(self.poll_interval)


def _cloud_data(response: httpx.Response, operation: str) -> Mapping[str, Any]:
    raise_for_parser_status("mineru cloud", response)
    payload = json_mapping("mineru cloud", response)
    code = payload.get("code")
    if code != 0:
        message = payload.get("msg") or f"{operation} failed with code={code}"
        raise ParserServiceError("mineru", response.status_code, str(message))
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ParserServiceError("mineru", response.status_code, f"{operation} returned no data")
    return cast(Mapping[str, Any], data)


def _required_cloud_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ParserServiceError("mineru", None, f"cloud response is missing {key}")
    return value


def _first_cloud_url(value: object) -> str:
    if not isinstance(value, list) or not value:
        raise ParserServiceError("mineru", None, "cloud response is missing file_urls")
    first = cast(list[object], value)[0]
    if not isinstance(first, str) or not first:
        raise ParserServiceError("mineru", None, "cloud response contains an invalid upload URL")
    return first


def _cloud_result_for_file(data: Mapping[str, Any], filename: str) -> Mapping[str, Any]:
    raw_results = data.get("extract_result")
    if not isinstance(raw_results, list) or not raw_results:
        return {"state": "pending"}
    results = [
        cast(Mapping[str, Any], item)
        for item in cast(list[object], raw_results)
        if isinstance(item, Mapping)
    ]
    if not results:
        return {"state": "pending"}
    return next(
        (item for item in results if item.get("file_name") == filename),
        results[0],
    )


def _is_zip_response(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "zip" in content_type or response.content.startswith(b"PK\x03\x04")


def _parse_archive(
    filename: str,
    content: bytes,
    *,
    parser_version: str | None,
) -> ParsedDocument:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = _safe_members(archive)
            markdown_member = _markdown_member(members)
            markdown = archive.read(markdown_member).decode("utf-8-sig")
            images_dir = _images_directory(members, markdown_member)
            assets: list[ParsedAsset] = []
            if images_dir is not None:
                for member in members:
                    path = PurePosixPath(member)
                    if (
                        not member.startswith(f"{images_dir}/")
                        or path.suffix.lower() not in _IMAGE_SUFFIXES
                    ):
                        continue
                    image = archive.read(member)
                    if len(image) > _MAX_IMAGE_BYTES:
                        raise ParserServiceError("mineru", None, f"image is too large: {member}")
                    relative_path = path.relative_to(PurePosixPath(images_dir))
                    source_path = f"images/{relative_path.as_posix()}"
                    assets.append(
                        ParsedAsset(
                            asset_index=len(assets),
                            source_path=source_path,
                            mime_type=infer_image_mime_type(source_path, image),
                            content=image,
                        )
                    )
    except (zipfile.BadZipFile, UnicodeDecodeError, KeyError) as exc:
        raise ParserServiceError("mineru", None, f"invalid ZIP response: {exc}") from exc

    return build_markdown_document(
        parser="mineru",
        filename=filename,
        markdown=markdown,
        assets=assets,
        parser_version=parser_version,
        metadata={"response_format": "zip"},
    )


def _safe_members(archive: zipfile.ZipFile) -> list[str]:
    infos = archive.infolist()
    if len(infos) > _MAX_ARCHIVE_FILES:
        raise ParserServiceError("mineru", None, "ZIP response contains too many files")
    if sum(info.file_size for info in infos) > _MAX_ARCHIVE_BYTES:
        raise ParserServiceError("mineru", None, "ZIP response is too large")

    members: list[str] = []
    for info in infos:
        member = info.filename.replace("\\", "/")
        path = PurePosixPath(member)
        if path.is_absolute() or ".." in path.parts:
            raise ParserServiceError("mineru", None, f"unsafe ZIP path: {info.filename}")
        if not info.is_dir():
            members.append(member)
    return members


def _markdown_member(members: list[str]) -> str:
    markdown_files = [member for member in members if member.lower().endswith(".md")]
    if not markdown_files:
        raise ParserServiceError("mineru", None, "ZIP response contains no Markdown file")
    return next(
        (member for member in markdown_files if PurePosixPath(member).name.lower() == "full.md"),
        markdown_files[0],
    )


def _images_directory(members: list[str], markdown_member: str) -> str | None:
    parent = PurePosixPath(markdown_member).parent
    candidates: list[PurePosixPath] = []
    if str(parent) != ".":
        candidates.extend((parent / "images", parent.parent / "images"))
    candidates.append(PurePosixPath("images"))
    for candidate in candidates:
        prefix = f"{candidate.as_posix().rstrip('/')}/"
        if any(member.startswith(prefix) for member in members):
            return candidate.as_posix().rstrip("/")
    return None
