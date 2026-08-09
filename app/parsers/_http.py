from collections.abc import Mapping
from typing import Any, cast

import httpx

from app.parsers.types import ParsedBlock, ParserServiceError

_TEXT_KEYS = ("text", "content", "markdown", "md_content")
_BLOCK_CANDIDATE_KEYS = ("blocks", "layoutParsingResults", "results")


def raise_for_parser_status(parser: str, response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    message = response.text[:500] if response.text else response.reason_phrase
    raise ParserServiceError(parser, response.status_code, message)


def json_mapping(parser: str, response: httpx.Response) -> Mapping[str, Any]:
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ParserServiceError(parser, response.status_code, "parser returned non-object JSON")
    return cast(Mapping[str, Any], payload)


def extract_version(payload: Mapping[str, Any]) -> str | None:
    for key in ("version", "parser_version", "pipeline_version", "pipelineVersion"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    result = payload.get("result")
    if isinstance(result, Mapping):
        return extract_version(cast(Mapping[str, Any], result))
    return None


def extract_blocks(parser: str, payload: Mapping[str, Any]) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    for raw_block in _iter_raw_blocks(payload):
        text = _extract_text(raw_block)
        if not text:
            continue
        blocks.append(
            ParsedBlock(
                text=text,
                block_index=len(blocks),
                block_type=_string_value(raw_block, "type", "block_type") or "paragraph",
                page_number=_int_value(raw_block, "page", "page_number", "pageNo", "page_no"),
                heading_path=_string_list_value(raw_block, "heading_path", "headings"),
                ocr_confidence=_float_value(raw_block, "ocr_confidence", "confidence"),
                coordinates=_float_list_value(raw_block, "coordinates", "bbox", "box"),
                metadata={"raw_type": _string_value(raw_block, "type", "block_type")},
            )
        )
    if not blocks:
        raise ParserServiceError(parser, None, "parser returned no text blocks")
    return blocks


def _iter_raw_blocks(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for candidate in _candidate_lists(payload):
        blocks: list[Mapping[str, Any]] = []
        for item in candidate:
            blocks.extend(_normalize_raw_block(item))
        if blocks:
            return blocks

    direct_text = _extract_text(payload)
    if direct_text:
        return [{"text": direct_text}]
    return []


def _candidate_lists(payload: Mapping[str, Any]) -> list[list[Any]]:
    candidates: list[list[Any]] = []
    for key in _BLOCK_CANDIDATE_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            candidates.append(cast(list[Any], value))

    result = payload.get("result")
    if isinstance(result, Mapping):
        result_mapping = cast(Mapping[str, Any], result)
        for key in _BLOCK_CANDIDATE_KEYS:
            value = result_mapping.get(key)
            if isinstance(value, list):
                candidates.append(cast(list[Any], value))
    return candidates


def _normalize_raw_block(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, str):
        return [{"text": value}]
    if not isinstance(value, Mapping):
        return []

    raw = cast(Mapping[str, Any], value)
    pruned = raw.get("prunedResult")
    if isinstance(pruned, list):
        normalized: list[Mapping[str, Any]] = []
        for item in cast(list[Any], pruned):
            child_blocks = _normalize_raw_block(item)
            for child in child_blocks:
                normalized.append(_merge_page_context(raw, child))
        return normalized
    if isinstance(pruned, Mapping):
        return [
            _merge_page_context(raw, child)
            for child in _normalize_raw_block(cast(Mapping[str, Any], pruned))
        ]
    if isinstance(pruned, str):
        return [_merge_page_context(raw, child) for child in _normalize_raw_block(pruned)]
    return [raw]


def _merge_page_context(parent: Mapping[str, Any], child: Mapping[str, Any]) -> Mapping[str, Any]:
    merged = dict(child)
    for key in ("page", "page_number", "pageNo", "page_no"):
        if key in parent and key not in merged:
            merged[key] = parent[key]
    return merged


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_extract_text(item) for item in cast(list[Any], value)]
        return "\n".join(part for part in parts if part)
    if isinstance(value, Mapping):
        raw = cast(Mapping[str, Any], value)
        for key in _TEXT_KEYS:
            text = raw.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
        pruned = raw.get("prunedResult")
        return _extract_text(pruned)
    return ""


def _string_value(raw: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _int_value(raw: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdecimal():
            return int(value)
    return None


def _float_value(raw: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _float_list_value(raw: Mapping[str, Any], *keys: str) -> list[float] | None:
    for key in keys:
        value = raw.get(key)
        if not isinstance(value, list):
            continue
        coordinates = [
            float(item) for item in cast(list[Any], value) if isinstance(item, int | float)
        ]
        if coordinates:
            return coordinates
    return None


def _string_list_value(raw: Mapping[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in cast(list[Any], value) if isinstance(item, str)]
    return []
