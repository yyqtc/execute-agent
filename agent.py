from langgraph.graph import StateGraph, START, END
from custom_type import PlanExecute
from plan_node import plan_node
from replan_node import replan_node
from code_execute_node import execute_node as code_execute_node
from normal_execute_node import execute_node as normal_execute_node
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
    agent.add_node("code_execute", code_execute_node)
    agent.add_node("normal_execute", normal_execute_node)

    def _choose_execute_node(state: PlanExecute):
        if "response" in state and state["response"]:
            return END
        else:
            # 延迟导入避免循环导入
            from agent_instance import assistant_choose_agent
            if assistant_choose_agent is None:
                logger.error("assistant_choose_agent 未初始化")
                return "normal_execute"
            result = assistant_choose_agent.invoke({"input": state["plan"][0]})
            result = result.content
            if result == "code_execute":
                return "code_execute"
            else:
                return "normal_execute"


    def _should_replan(state: PlanExecute):
        if "response" in state and state["response"]:
            return END
        else:
            return "replan"

    agent.add_edge(START, "plan")
    agent.add_conditional_edges(
        "plan", _choose_execute_node, ["normal_execute", "code_execute", END]
    )
    agent.add_conditional_edges("code_execute", _should_replan, ["replan", END])
    agent.add_conditional_edges("normal_execute", _should_replan, ["replan", END])
    agent.add_conditional_edges(
        "replan", _choose_execute_node, ["normal_execute", "code_execute", END]
    )

    app = agent.compile()

    return app


async def main():
    agent = await initialize_graph()
    result = await agent.ainvoke({"input": "你好", "index": 0})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
