from langchain.agents.middleware import before_model, after_model, SummarizationMiddleware
from langchain_core.messages.utils import trim_messages
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain.agents import AgentState
from langgraph.runtime import Runtime
from load_config import config
from typing import List

import threading
import logging
import tiktoken

logger = logging.getLogger(__name__)
enc = tiktoken.get_encoding("cl100k_base")

# 线程本地存储，用于存储每个线程的 SafeFileWriter 实例
_thread_local = threading.local()

def get_file_writer():
    """
    获取当前线程的 SafeFileWriter 实例

    Returns:
        SafeFileWriter 实例，如果未设置则返回 None
    """
    return getattr(_thread_local, "file_writer", None)


def set_file_writer(file_writer):
    """
    设置当前线程的 SafeFileWriter 实例

    Args:
        file_writer: SafeFileWriter 实例
    """
    _thread_local.file_writer = file_writer


def get_token_count(messages: List[BaseMessage]) -> int:
    total_tokens = 0
    for message in messages:
        message_str = f"{message.type}\n{message.content}"
        total_tokens += len(enc.encode(message_str))
        if hasattr(message, "name") and message.name:
            total_tokens += len(enc.encode(message.name))

    total_tokens += len(messages)

    return total_tokens


@before_model
def inject_file_writer_middleware(state: AgentState, runtime: Runtime) -> AgentState:
    """
    中间件函数：在模型调用之前注入 SafeFileWriter 实例到上下文

    从 state 的 configurable 中获取 file_writer，并将其存储到线程本地存储中，
    以便工具函数可以访问。

    注意：如果 configurable 中没有提供 file_writer，不会清除已存在的 file_writer
    （可能已在 main.py 中设置）。

    Args:
        state: AgentState 对象，包含 agent 的状态信息

    Returns:
        修改后的 AgentState 对象
    """
    try:
        # 尝试从 state 中获取 configurable
        # state 可能是字典或特殊对象
        if isinstance(state, dict):
            configurable = state.get("configurable", {})
        elif hasattr(state, "configurable"):
            configurable = state.configurable
        elif hasattr(state, "get"):
            configurable = state.get("configurable", {})
        else:
            # 如果无法获取 configurable，记录日志但不报错
            print(f"无法从 state 中获取 configurable，state 类型: {type(state)}")
            return state

        # 如果 configurable 是字典，尝试从中获取 file_writer
        if isinstance(configurable, dict):
            file_writer = configurable.get("file_writer")
            if file_writer is not None:
                # 将 file_writer 存储到线程本地存储中
                set_file_writer(file_writer)
                print("已从 configurable 注入 SafeFileWriter 实例到线程本地存储")
            else:
                # 如果没有提供 file_writer，检查是否已经存在（可能已在 main.py 中设置）
                existing_writer = get_file_writer()
                if existing_writer is None:
                    print("configurable 中未找到 file_writer，且线程本地存储中也没有")
        else:
            print(f"configurable 不是字典类型: {type(configurable)}")

    except Exception as e:
        print(f"中间件处理 file_writer 时发生错误: {e}", exc_info=True)

    return state


@after_model
def cleanup_file_writer_middleware(state: AgentState, runtime: Runtime) -> AgentState:
    """
    中间件函数：在模型调用之后清理线程本地存储（可选）

    这个函数主要用于清理，确保不会泄露资源。
    实际上，线程本地存储会在线程结束时自动清理，所以这个函数是可选的。

    Args:
        state: AgentState 对象

    Returns:
        AgentState 对象（未修改）
    """
    # 可以选择在这里清理，但通常不需要
    # 因为线程本地存储会在线程结束时自动清理
    return state


@before_model
def trim_long_messages_middleware(state: AgentState, runtime: Runtime) -> AgentState:
    """
    中间件函数：在模型调用之前修剪过长消息
    """
    messages = state.get("messages", [])
    trimmed = trim_messages(
        messages,
        token_counter=get_token_count,
        strategy="last",  # 保留最后的消息
        max_tokens=config["SUMMARY_THRESHOLD"],  # 设置为模型允许的最大值
        start_on="human",
        end_on=("human", "tool"),
    )
    if len(trimmed) < len(messages):
        return {"messages": trimmed}
    else:
        return None


middlewares = [
    inject_file_writer_middleware, 
    cleanup_file_writer_middleware,
    trim_long_messages_middleware,
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
