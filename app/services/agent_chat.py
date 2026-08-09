from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from app.agent.state import AgentEvidence


class AgentGraphProtocol(Protocol):
    async def ainvoke(
        self,
        graph_input: Any,
        config: Any,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    content: str
    citations: list[AgentEvidence]


class AgentChatService:
    def __init__(self, *, graph: AgentGraphProtocol) -> None:
        self._graph = graph

    async def answer(self, *, knowledge_base_id: uuid.UUID, query: str) -> AgentAnswer:
        result = cast(
            Mapping[str, object],
            await self._graph.ainvoke(
                {"query": query, "knowledge_base_id": str(knowledge_base_id)},
                {"configurable": {"thread_id": f"agent-{uuid.uuid4()}"}},
            ),
        )
        return AgentAnswer(
            content=str(result.get("final_answer", "")),
            citations=_agent_evidence_list(result.get("evidence", [])),
        )


def _agent_evidence_list(value: object) -> list[AgentEvidence]:
    if not isinstance(value, list):
        return []
    items = cast(list[Any], value)
    return [item for item in items if isinstance(item, AgentEvidence)]
