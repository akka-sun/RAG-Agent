from __future__ import annotations

import uuid
from typing import Protocol

from app.agent.state import AgentEvidence
from app.services.retrieval import RetrievalAnswerContext


class RetrievalServiceProtocol(Protocol):
    async def query(
        self,
        *,
        knowledge_base_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> RetrievalAnswerContext: ...


class RetrievalTool:
    def __init__(self, *, service: RetrievalServiceProtocol, limit: int) -> None:
        self._service = service
        self._limit = limit

    async def run(self, *, knowledge_base_id: uuid.UUID, query: str) -> list[AgentEvidence]:
        context = await self._service.query(
            knowledge_base_id=knowledge_base_id,
            query=query,
            limit=self._limit,
        )
        return [
            AgentEvidence(
                label=item.label or f"S{index}",
                document_id=item.document_id,
                filename=item.filename,
                chunk_id=item.chunk_id,
                text=item.text,
                start=item.start,
                end=item.end,
                score=item.score,
                page_number=item.page_number,
                section=item.section,
                metadata=item.metadata,
            )
            for index, item in enumerate(context.evidence, start=1)
        ]
