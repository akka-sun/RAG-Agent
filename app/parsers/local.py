import re

from app.parsers.types import ParsedBlock, ParsedDocument

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_markdown(filename: str, content: bytes) -> ParsedDocument:
    text = _decode_utf8(content)
    blocks: list[ParsedBlock] = []
    heading_path: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        paragraph = " ".join(line.strip() for line in paragraph_lines).strip()
        paragraph_lines.clear()
        if not paragraph:
            return
        blocks.append(
            ParsedBlock(
                text=paragraph,
                block_index=len(blocks),
                heading_path=list(heading_path),
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        heading = _HEADING_RE.match(line)
        if heading is not None:
            flush_paragraph()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_path = heading_path[: level - 1]
            heading_path.append(title)
            continue
        if not line:
            flush_paragraph()
            continue
        paragraph_lines.append(line)

    flush_paragraph()
    _reject_empty_blocks(blocks)
    return ParsedDocument(
        parser="local",
        source_format="md",
        blocks=blocks,
        parser_version="local-v1",
        metadata={"filename": filename},
    )


def parse_txt(filename: str, content: bytes) -> ParsedDocument:
    text = _decode_utf8(content)
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
        if paragraph.strip()
    ]
    blocks = [
        ParsedBlock(
            text=paragraph,
            block_index=index,
        )
        for index, paragraph in enumerate(paragraphs)
    ]
    _reject_empty_blocks(blocks)
    return ParsedDocument(
        parser="local",
        source_format="txt",
        blocks=blocks,
        parser_version="local-v1",
        metadata={"filename": filename},
    )


def _decode_utf8(content: bytes) -> str:
    text = content.decode("utf-8").strip()
    if not text:
        raise ValueError("empty document")
    return text


def _reject_empty_blocks(blocks: list[ParsedBlock]) -> None:
    if not blocks:
        raise ValueError("empty document")
