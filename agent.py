from langgraph.graph import StateGraph, START, END
from custom_type import PlanExecute
from plan_node import plan_node
from replan_node import replan_node
from execute_node import execute_node
from agent_instance import initial_agent
from tools_registry import get_execute_tools

import asyncio
import logging

logger = logging.getLogger(__name__)


async def initialize_graph():
    # 初始化 agent（必须在创建 graph 之前）
    tools = await get_execute_tools()
    await initial_agent(tools)
    
    agent = StateGraph(PlanExecute)
    agent.add_node("plan", plan_node)
    agent.add_node("replan", replan_node)
    agent.add_node("execute", execute_node)

    def _should_end(state: PlanExecute):
        if "response" in state and state["response"].strip():
            return END
        else:
            return "execute"

    agent.add_edge(START, "plan")
    agent.add_edge("plan", "execute")
    agent.add_edge("execute", "replan")
    agent.add_conditional_edges(
        "replan", _should_end, ["execute", END]
    )

    app = agent.compile()

    return app


async def main():
    agent = await initialize_graph()
    result = await agent.ainvoke({"input": "你好", "index": 0})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
