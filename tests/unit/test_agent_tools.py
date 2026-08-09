import uuid

import pytest

from app.agent.tools import RetrievalTool
from app.services.retrieval import RetrievalAnswerContext, RetrievalEvidence


class FakeRetrievalService:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.knowledge_base_ids: list[uuid.UUID] = []
        self.limits: list[int] = []

    async def query(
        self,
        *,
        knowledge_base_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> RetrievalAnswerContext:
        self.knowledge_base_ids.append(knowledge_base_id)
        self.queries.append(query)
        self.limits.append(limit)
        return RetrievalAnswerContext(
            answer="retrieved answer",
            evidence=[
                RetrievalEvidence(
                    label="S1",
                    document_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    filename="policy.md",
                    chunk_id="chunk-1",
                    text="retrieved text",
                    start=0,
                    end=14,
                    score=0.95,
                )
            ],
        )


@pytest.mark.asyncio
async def test_retrieval_tool_returns_agent_evidence_from_hybrid_retrieval() -> None:
    service = FakeRetrievalService()
    tool = RetrievalTool(service=service, limit=4)
    kb_id = uuid.uuid4()

    evidence = await tool.run(knowledge_base_id=kb_id, query="pricing")

    assert service.knowledge_base_ids == [kb_id]
    assert service.queries == ["pricing"]
    assert service.limits == [4]
    assert evidence[0].label == "S1"
    assert evidence[0].text == "retrieved text"
    assert evidence[0].document_id == uuid.UUID("22222222-2222-2222-2222-222222222222")
