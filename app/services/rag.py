import uuid

from app.rag.chunking import chunk_text
from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.rag.types import IndexedChunk
from app.schemas.rag import (
    RAGDocumentCreate,
    RAGDocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSourceResponse,
)
from app.services.knowledge_base import KnowledgeBaseService


class RAGService:
    def __init__(
        self,
        knowledge_base_service: KnowledgeBaseService,
        store: InMemoryVectorStore,
        embedder: HashingEmbedder,
        chunk_size: int = 500,
        overlap: int = 100,
    ) -> None:
        self._knowledge_base_service = knowledge_base_service
        self._store = store
        self._embedder = embedder
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def ingest(
        self,
        data: RAGDocumentCreate,
    ) -> RAGDocumentResponse:
        await self._knowledge_base_service.get(data.knowledge_base_id)

        document_id = uuid.uuid4()

        chunks = chunk_text(
            data.content,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
        )

        indexed_chunks = [
            IndexedChunk(
                knowledge_base_id=data.knowledge_base_id,
                document_id=document_id,
                filename=data.filename,
                chunk_id=f"{document_id}:{chunk.index}",
                text=chunk.text,
                start=chunk.start,
                end=chunk.end,
                vector=self._embedder.embed(chunk.text),
            )
            for chunk in chunks
        ]

        self._store.add(indexed_chunks)

        return RAGDocumentResponse(
            document_id=document_id,
            chunk_count=len(chunks),
        )

    async def query(
        self,
        data: RAGQueryRequest,
    ) -> RAGQueryResponse:
        await self._knowledge_base_service.get(data.knowledge_base_id)

        query_vector = self._embedder.embed(data.query)

        results = self._store.search(
            data.knowledge_base_id,
            query_vector,
            data.top_k,
        )

        if not results:
            return RAGQueryResponse(
                answer="未找到相关证据。",
                sources=[],
            )

        sources = [
            RAGSourceResponse(
                label=f"S{index}",
                document_id=result.chunk.document_id,
                filename=result.chunk.filename,
                chunk_id=result.chunk.chunk_id,
                text=result.chunk.text,
                start=result.chunk.start,
                end=result.chunk.end,
                score=result.score,
            )
            for index, result in enumerate(
                results,
                start=1,
            )
        ]

        answer_lines = [
            "根据检索到的资料：",
            *[f"[{source.label}] {source.text}" for source in sources],
        ]

        return RAGQueryResponse(
            answer="\n".join(answer_lines),
            sources=sources,
        )
