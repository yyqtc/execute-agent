from langchain.agents.middleware import SummarizationMiddleware
from langchain_openai import ChatOpenAI

import json
import os

if not os.path.exists("config.json"):
    raise FileNotFoundError("config.json not found")

config = {}
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

middlewares = [
    SummarizationMiddleware(
        model=ChatOpenAI(
            model=config["SUMMARY_LLM_MODEL"],
            openai_api_key=config["LLM_API_KEY"],
            openai_api_base=config["LLM_API_BASE"],
            temperature=0.3,
        ),
        max_tokens_before_summary=config["SUMMARY_THRESHOLD"],
        summary_prompt=f"请把内容长度适当总结，不要遗漏重要消息（未完成的功能、项目的结构、项目的依赖、项目中未解决的错误）的前提下，适当压缩其他信息，把内容长度控制在{config['SUMMARY_MAX_LENGTH']}个token以内。"
    ),
]
