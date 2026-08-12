from app.parsers.types import ParsedBlock, ParsedDocument
from app.rag.types import TextChunk


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0

    while start < len(normalized):
        end = min(
            start + chunk_size,
            len(normalized),
        )

        chunks.append(
            TextChunk(
                index=len(chunks),
                text=normalized[start:end],
                start=start,
                end=end,
            )
        )

        if end == len(normalized):
            break

        start = end - overlap

    return chunks


def chunk_parsed_document(
    parsed: ParsedDocument,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    cursor = 0
    for block in parsed.blocks:
        block_text = block.text.strip()
        if not block_text:
            continue
        metadata = _block_metadata(parsed, block)
        for chunk in chunk_text(block_text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=chunk.text,
                    start=cursor + chunk.start,
                    end=cursor + chunk.end,
                    metadata=metadata,
                )
            )
        cursor += len(block_text) + 1
    return chunks


def _block_metadata(parsed: ParsedDocument, block: ParsedBlock) -> dict[str, object]:
    metadata: dict[str, object] = {
        "parser": parsed.parser,
        "source_format": parsed.source_format,
        "block_index": block.block_index,
        "block_type": block.block_type,
    }
    section = " > ".join(block.heading_path)
    if section:
        metadata["section"] = section
    if parsed.parser_version is not None:
        metadata["parser_version"] = parsed.parser_version
    if block.page_number is not None:
        metadata["page_number"] = block.page_number
    if block.heading_path:
        metadata["heading_path"] = list(block.heading_path)
    if block.ocr_confidence is not None:
        metadata["ocr_confidence"] = block.ocr_confidence
    if block.coordinates is not None:
        metadata["coordinates"] = list(block.coordinates)
    metadata.update(block.metadata)
    return metadata
