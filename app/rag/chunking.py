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
