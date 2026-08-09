import uuid
from typing import Any

import pytest

from app.agent.state import AgentEvidence
from app.services.agent_chat import AgentChatService


class FakeAgentGraph:
    def __init__(self) -> None:
        self.inputs: list[dict[str, object]] = []
        self.configs: list[dict[str, Any]] = []

    async def ainvoke(
        self,
        graph_input: dict[str, object],
        config: dict[str, Any],
    ) -> dict[str, object]:
        self.inputs.append(graph_input)
        self.configs.append(config)
        return {
            "final_answer": "final answer",
            "evidence": [
                AgentEvidence(
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
        }


@pytest.mark.asyncio
async def test_agent_chat_service_returns_answer_and_evidence() -> None:
    graph = FakeAgentGraph()
    service = AgentChatService(graph=graph)
    kb_id = uuid.uuid4()

    answer = await service.answer(knowledge_base_id=kb_id, query="What changed?")

    assert answer.content == "final answer"
    assert answer.citations[0].label == "S1"
    assert graph.inputs == [{"query": "What changed?", "knowledge_base_id": str(kb_id)}]
    assert graph.configs[0]["configurable"]["thread_id"]
