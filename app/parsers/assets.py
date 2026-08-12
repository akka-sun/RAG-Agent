from __future__ import annotations

import json
import mimetypes
import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any, cast
from urllib.parse import unquote

from app.parsers.local import parse_markdown
from app.parsers.types import ParsedAsset, ParsedDocument, ParserName

_MARKDOWN_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\(\s*)(<[^>\n]+>|[^\s)\n]+)([^)\n]*\))")


def build_markdown_document(
    *,
    parser: ParserName,
    filename: str,
    markdown: str,
    assets: list[ParsedAsset],
    parser_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ParsedDocument:
    local = parse_markdown(filename, markdown.encode("utf-8"))
    return ParsedDocument(
        parser=parser,
        source_format="pdf",
        blocks=local.blocks,
        markdown=markdown.strip(),
        assets=assets,
        parser_version=parser_version,
        metadata={"filename": filename, **(metadata or {})},
    )


def rewrite_document_asset_urls(
    parsed: ParsedDocument,
    assets: list[ParsedAsset],
) -> ParsedDocument:
    replacements: list[tuple[str, str]] = []
    for asset in assets:
        if asset.url is None:
            continue
        replacements.append((asset.source_path, asset.url))
        source_url = asset.metadata.get("source_url")
        if isinstance(source_url, str) and source_url:
            replacements.append((source_url, asset.url))

    markdown = (
        replace_markdown_image_links(parsed.markdown, replacements)
        if parsed.markdown is not None
        else None
    )
    blocks = [
        block.model_copy(update={"text": replace_markdown_image_links(block.text, replacements)})
        for block in parsed.blocks
    ]
    return parsed.model_copy(update={"markdown": markdown, "blocks": blocks, "assets": assets})


def replace_markdown_image_links(
    markdown: str,
    replacements: Sequence[tuple[str, str]],
) -> str:
    if not replacements:
        return markdown

    def replace(match: re.Match[str]) -> str:
        raw_destination = match.group(2)
        destination = raw_destination[1:-1] if raw_destination.startswith("<") else raw_destination
        replacement = _find_replacement(destination, replacements)
        if replacement is None:
            return match.group(0)
        return f"{match.group(1)}{replacement}{match.group(3)}"

    return _MARKDOWN_IMAGE_RE.sub(replace, markdown)


def infer_image_mime_type(path: str, content: bytes, declared: str | None = None) -> str:
    if declared:
        normalized = declared.split(";", maxsplit=1)[0].strip().lower()
        if normalized.startswith("image/"):
            return normalized
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    guessed, _ = mimetypes.guess_type(path)
    return guessed if guessed and guessed.startswith("image/") else "application/octet-stream"


def asset_keys_from_parsed(content: bytes) -> list[str]:
    assets = _manifest_assets(content)
    keys: list[str] = []
    for asset in assets:
        object_key = asset.get("object_key")
        if isinstance(object_key, str) and object_key and object_key not in keys:
            keys.append(object_key)
    return keys


def stored_asset_from_parsed(content: bytes, asset_index: int) -> tuple[str, str] | None:
    for asset in _manifest_assets(content):
        if asset.get("asset_index") != asset_index:
            continue
        object_key = asset.get("object_key")
        mime_type = asset.get("mime_type")
        if isinstance(object_key, str) and object_key and isinstance(mime_type, str):
            return object_key, mime_type
    return None


def _find_replacement(
    destination: str,
    replacements: Sequence[tuple[str, str]],
) -> str | None:
    normalized_destination = _normalize_reference(destination)
    destination_name = PurePosixPath(normalized_destination).name
    for source, replacement in replacements:
        normalized_source = _normalize_reference(source)
        if normalized_destination in {normalized_source, f"/{normalized_source}"}:
            return replacement
        if normalized_destination.endswith(f"/{normalized_source}"):
            return replacement
        if destination_name and destination_name == PurePosixPath(normalized_source).name:
            return replacement
    return None


def _normalize_reference(value: str) -> str:
    return unquote(value).replace("\\", "/").removeprefix("./").strip()


def _manifest_assets(content: bytes) -> list[Mapping[str, object]]:
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, Mapping):
        return []
    payload_mapping = cast(Mapping[str, object], payload)
    raw_assets = payload_mapping.get("assets")
    if not isinstance(raw_assets, list):
        return []
    return [
        cast(Mapping[str, object], item)
        for item in cast(list[object], raw_assets)
        if isinstance(item, Mapping)
    ]
