import os
from typing import TypedDict

import pytest
from backend.configs.settings import load_settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ApprovalState(TypedDict):
    decision: str


def wait_for_approval(state: ApprovalState) -> dict[str, str]:
    decision = interrupt({"decision": state["decision"]})
    return {"decision": decision["decision"]}


def create_approval_graph(checkpointer: AsyncPostgresSaver):
    builder = StateGraph(ApprovalState)
    builder.add_node("approval", wait_for_approval)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    return builder.compile(checkpointer=checkpointer)


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="requires an explicitly enabled PostgreSQL integration environment",
)
@pytest.mark.anyio
async def test_postgres_checkpoint_resumes_after_reopening_database() -> None:
    database_url = load_settings().database_url
    config = {"configurable": {"thread_id": "thread-1"}}

    async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
        await saver.setup()
        interrupted = await create_approval_graph(saver).ainvoke(
            {"decision": "pending"}, config=config
        )

    assert "__interrupt__" in interrupted

    async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
        await saver.setup()
        resumed = await create_approval_graph(saver).ainvoke(
            Command(resume={"decision": "approved"}), config=config
        )

    assert resumed["decision"] == "approved"
