import uuid
from collections.abc import Sequence
from typing import Any, cast

import pytest

from app.agent.graph import build_agent_graph
from app.agent.state import AgentEvidence
from app.infrastructure.chat_client import ChatCompletionResult, ChatMessage


class AlwaysRequestsMoreRetrievalClient:
    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        del messages
        return ChatCompletionResult(content="NEED_MORE")


class FakeRetrievalTool:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def run(self, *, knowledge_base_id: uuid.UUID, query: str) -> list[AgentEvidence]:
        del knowledge_base_id
        self.queries.append(query)
        return [
            AgentEvidence(
                label=f"S{len(self.queries)}",
                document_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                filename="policy.md",
                chunk_id=f"chunk-{len(self.queries)}",
                text="partial evidence",
                start=0,
                end=16,
                score=0.5,
            )
        ]


class DirectAnswerClient:
    def __init__(self) -> None:
        self.responses = ["DIRECT", "direct answer"]

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        del messages
        return ChatCompletionResult(content=self.responses.pop(0))


@pytest.mark.asyncio
async def test_agent_stops_after_three_retrieval_attempts() -> None:
    retrieval_tool = FakeRetrievalTool()
    graph = build_agent_graph(
        chat_client=AlwaysRequestsMoreRetrievalClient(),
        retrieval_tool=retrieval_tool,
        max_retrievals=3,
    )

    result = cast(
        dict[str, object],
        await cast(Any, graph).ainvoke(
            {"query": "hard question", "knowledge_base_id": str(uuid.uuid4())}
        ),
    )

    assert result["retrieval_count"] == 3
    assert len(retrieval_tool.queries) == 3
    assert "insufficient evidence" in cast(str, result["final_answer"]).lower()


@pytest.mark.asyncio
async def test_agent_can_answer_without_retrieval_when_classified_direct() -> None:
    retrieval_tool = FakeRetrievalTool()
    graph = build_agent_graph(
        chat_client=DirectAnswerClient(),
        retrieval_tool=retrieval_tool,
        max_retrievals=3,
    )

    result = cast(
        dict[str, object],
        await cast(Any, graph).ainvoke(
            {"query": "say hello", "knowledge_base_id": str(uuid.uuid4())}
        ),
    )

    assert result["retrieval_count"] == 0
    assert retrieval_tool.queries == []
    assert result["final_answer"] == "direct answer"
