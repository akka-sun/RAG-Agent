# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
import uuid
from typing import Any, TypedDict, cast

import pytest
from langgraph.graph import END, START, StateGraph

from app.agent.checkpoint import create_async_checkpointer, setup_checkpointer
from app.config import get_settings


class CheckpointTestState(TypedDict):
    value: str


@pytest.mark.asyncio
async def test_checkpointer_writes_and_reads_real_postgres_checkpoint() -> None:
    database_url = get_settings().test_database_url
    await setup_checkpointer(database_url)

    graph = StateGraph(CheckpointTestState)

    async def write_value(state: CheckpointTestState) -> CheckpointTestState:
        del state
        return {"value": "stored"}

    graph.add_node("write_value", write_value)
    graph.add_edge(START, "write_value")
    graph.add_edge("write_value", END)
    thread_id = f"checkpoint-test-{uuid.uuid4()}"
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    async with create_async_checkpointer(database_url) as checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)

        result = cast(
            dict[str, object],
            await cast(Any, compiled).ainvoke({"value": "initial"}, config),
        )
        stored = await checkpointer.aget(cast(Any, config))

    assert result["value"] == "stored"
    assert stored is not None
