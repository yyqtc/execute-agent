from .tools import codebase_search
from .custom_type import VuePlanExecute, VuePlan
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

import asyncio
import logging
import json
import os

logger = logging.getLogger(__name__)

if not os.path.exists("config.json"):
    raise FileNotFoundError("config.json not found")

config = {}
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

_model = ChatOpenAI(
    model=config.get("PLAN_LLM_MODEL", "qwen-plus"),
    openai_api_key=config["LLM_API_KEY"],
    openai_api_base=config["LLM_API_BASE"],
    temperature=0.15
)

_prompt = """
你是一个擅长根据用户需求分析那些文件需要被读取、被修改和被创建的助手。
你需要根据交给你的业务需求，梳理一个文件读取、修改和创建的计划，用来指导后续生成和应用patch。
你输出的数据结构必须严格按照json格式规范，包含steps字段，steps字段是一个数组，数组中的每个项包含三个信息：文件名、操作类型和操作目的。
文件名是一个绝对路径，操作类型取值范围是：create、edit、delete、rename、move和copy，操作目的是一段自然语言描述对文件操作的目的。
"""

plan_agent = create_agent(
    model=_model,
    system_prompt=_prompt,
    tools=[codebase_search],
    response_format=VuePlan
)

async def plan_node(state: VuePlanExecute) -> VuePlanExecute:
    result = await plan_agent.ainvoke({
        "messages": [{"role": "user", "content": state["input"]}]
    })
    result = result.get("structured_response", None)
    if result is None:
        return {
            "response": "计划生成失败，返回为空"
        }
    else:
        return {
            "steps": result.steps
        }


if __name__ == "__main__":
    print(asyncio.run(plan_node({"input": "在/frontend目录下创建一个简单的Vue 3项目"})))
