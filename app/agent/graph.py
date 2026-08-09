# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.state import AgentEvidence, AgentState
from app.infrastructure.chat_client import ChatCompletionResult, ChatMessage


class ChatClientProtocol(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult: ...


class RetrievalToolProtocol(Protocol):
    async def run(self, *, knowledge_base_id: uuid.UUID, query: str) -> list[AgentEvidence]: ...


Route = Literal["retrieve", "generate"]


def build_agent_graph(
    *,
    chat_client: ChatClientProtocol,
    retrieval_tool: RetrievalToolProtocol,
    max_retrievals: int,
    checkpointer: Any | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    retrieval_limit = max(max_retrievals, 0)
    graph = StateGraph(AgentState)

    async def classify(state: AgentState) -> AgentState:
        query = _query_from_state(state)
        result = await chat_client.complete(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "Decide whether the user question needs knowledge-base retrieval. "
                        "Return exactly DIRECT or RETRIEVE."
                    ),
                ),
                ChatMessage(role="user", content=query),
            ]
        )
        classification = "DIRECT" if result.content.strip().upper() == "DIRECT" else "RETRIEVE"
        return {
            "normalized_query": query,
            "classification": classification,
            "retrieval_count": int(state.get("retrieval_count", 0)),
            "evidence": list(state.get("evidence", [])),
        }

    async def maybe_rewrite(state: AgentState) -> AgentState:
        query = _query_from_state(state)
        result = await chat_client.complete(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "Rewrite the question as a concise retrieval query. "
                        "Return only the rewritten query."
                    ),
                ),
                ChatMessage(role="user", content=query),
            ]
        )
        return {"normalized_query": _usable_rewrite(result.content, fallback=query)}

    async def retrieve(state: AgentState) -> AgentState:
        query = _query_from_state(state)
        knowledge_base_id = _knowledge_base_id_from_state(state)
        new_evidence = await retrieval_tool.run(
            knowledge_base_id=knowledge_base_id,
            query=query,
        )
        existing_evidence = list(state.get("evidence", []))
        return {
            "retrieval_count": int(state.get("retrieval_count", 0)) + 1,
            "evidence": existing_evidence + new_evidence,
        }

    async def decide(state: AgentState) -> AgentState:
        if int(state.get("retrieval_count", 0)) >= retrieval_limit:
            return {"needs_more_evidence": True}
        result = await chat_client.complete(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "Decide whether the evidence is enough to answer. "
                        "Return exactly ENOUGH or NEED_MORE."
                    ),
                ),
                ChatMessage(
                    role="user",
                    content=_decision_prompt(
                        query=_query_from_state(state),
                        evidence=list(state.get("evidence", [])),
                    ),
                ),
            ]
        )
        return {"needs_more_evidence": result.content.strip().upper() == "NEED_MORE"}

    async def generate(state: AgentState) -> AgentState:
        if _needs_more_evidence(state) and int(state.get("retrieval_count", 0)) >= retrieval_limit:
            return {
                "final_answer": (
                    f"Insufficient evidence after {state.get('retrieval_count', 0)} "
                    "retrieval attempts."
                )
            }

        result = await chat_client.complete(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "Answer the user using the provided evidence. "
                        "Cite sources with labels like [S1] when evidence is available."
                    ),
                ),
                ChatMessage(
                    role="user",
                    content=_answer_prompt(
                        query=_query_from_state(state),
                        evidence=list(state.get("evidence", [])),
                    ),
                ),
            ]
        )
        return {"final_answer": result.content.strip()}

    def route_after_classify(state: AgentState) -> Route:
        if state.get("classification") == "DIRECT" or retrieval_limit <= 0:
            return "generate"
        return "retrieve"

    def route_after_decide(state: AgentState) -> Route:
        if _needs_more_evidence(state) and int(state.get("retrieval_count", 0)) < retrieval_limit:
            return "retrieve"
        return "generate"

    graph.add_node("classify", classify)
    graph.add_node("maybe_rewrite", maybe_rewrite)
    graph.add_node("retrieve", retrieve)
    graph.add_node("decide", decide)
    graph.add_node("generate", generate)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"retrieve": "maybe_rewrite", "generate": "generate"},
    )
    graph.add_edge("maybe_rewrite", "retrieve")
    graph.add_edge("retrieve", "decide")
    graph.add_conditional_edges(
        "decide",
        route_after_decide,
        {"retrieve": "retrieve", "generate": "generate"},
    )
    graph.add_edge("generate", END)
    return graph.compile(checkpointer=checkpointer)


def _query_from_state(state: AgentState) -> str:
    return str(state.get("normalized_query") or state.get("query") or "").strip()


def _knowledge_base_id_from_state(state: AgentState) -> uuid.UUID:
    value = state.get("knowledge_base_id")
    if value is None:
        msg = "agent state requires knowledge_base_id"
        raise ValueError(msg)
    return uuid.UUID(str(value))


def _needs_more_evidence(state: AgentState) -> bool:
    return bool(state.get("needs_more_evidence", False))


def _usable_rewrite(value: str, *, fallback: str) -> str:
    candidate = value.strip()
    if not candidate or candidate.upper() in {"DIRECT", "RETRIEVE", "ENOUGH", "NEED_MORE"}:
        return fallback
    return candidate


def _decision_prompt(*, query: str, evidence: list[AgentEvidence]) -> str:
    return "\n".join(
        [
            f"Question: {query}",
            "Evidence:",
            *_evidence_lines(evidence),
        ]
    )


def _answer_prompt(*, query: str, evidence: list[AgentEvidence]) -> str:
    return "\n".join(
        [
            f"Question: {query}",
            "Evidence:",
            *_evidence_lines(evidence),
        ]
    )


def _evidence_lines(evidence: list[AgentEvidence]) -> list[str]:
    if not evidence:
        return ["No evidence retrieved."]
    return [f"[{item.label}] {item.text}" for item in evidence]
