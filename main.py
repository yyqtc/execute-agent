#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execute Agent 主入口文件
项目启动点，负责初始化并启动智能体
"""

import logging

logger = logging.getLogger(__name__)

import os
import sys
import asyncio
import traceback
import argparse

from load_config import config
from pathlib import Path

try:
    import agent
    from middleware import set_file_writer
    from utils.path_parser import process_at_paths
except ImportError as e:
    print("错误: 无法导入 agent 模块")
    print(f"   详细信息: {e}")
    sys.exit(1)
except Exception as e:
    print("错误: 导入 agent 模块时发生异常")
    print(f"   详细信息: {e}")
    traceback.print_exc()
    sys.exit(1)


class SafeFileWriter:
    """
    安全的文件写入器，确保不会写入父目录
    在 print 模式下禁用所有写入操作（除非 force=True）
    """

    def __init__(self, print_mode: bool, current_dir: Path, force: bool = False):
        self.print_mode = print_mode
        self.current_dir = current_dir.resolve()
        self.force = force

    def is_safe_path(self, file_path: Path) -> bool:
        """
        检查文件路径是否安全（在当前目录内）
        """
        try:
            resolved_path = file_path.resolve()
            # 检查路径是否在当前目录或其子目录中
            return resolved_path.is_relative_to(self.current_dir)
        except (ValueError, RuntimeError):
            return False

    def write(self, file_path: str, content: str, force: bool = False) -> bool:
        """
        安全地写入文件
        在 print 模式下只输出建议，不实际写入（除非 force=True）

        Args:
            file_path: 要写入的文件路径
            content: 要写入的内容
            force: 是否强制执行写入操作（默认为 False）
                   当 force=True 时，即使在 print_mode 下也会实际写入文件

        Returns:
            bool: 是否成功写入文件
        """
        path = Path(file_path)

        # 检查路径是否安全（无论是否在 print_mode 下都要检查）
        if not self.is_safe_path(path):
            raise ValueError(
                f"错误: 不允许写入父目录。"
                f"目标路径: {path.resolve()}, 当前目录: {self.current_dir}"
            )

        # 如果处于 print_mode 且未强制写入，则只输出建议
        if self.print_mode and not (self.force or force):
            return False

        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return True


def parse_arguments():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(
        description="Execute Agent - 智能代码执行助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s "任务描述"                      # 通过位置参数提供任务描述
  %(prog)s -p                              # 启用打印模式，仅输出建议
  %(prog)s --prompt "任务描述"             # 通过 --prompt 参数提供任务描述
  %(prog)s -P "任务描述"                   # 通过 -P 参数提供任务描述（--prompt 的简写）
  %(prog)s --prompt-file /absolute/path/to/prompt.txt  # 从文件读取提示词（必须是绝对路径）
  %(prog)s --force                        # 强制执行，不提示确认
  %(prog)s --output-format json           # 以 JSON 格式输出
  %(prog)s --output-format stream-json    # 以流式 JSON 格式输出（JSON Lines）
  %(prog)s --stream-partial-output        # 启用流式输出
  %(prog)s --prompt "任务描述" -p --output-format json  # 组合使用多个参数
        """,
    )

    parser.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="启用打印模式，用于非交互式脚本和自动化场景，仅输出建议而不修改文件",
    )

    parser.add_argument(
        "-P",
        "--prompt",
        type=str,
        help="指定任务描述（prompt），替代位置参数",
    )

    parser.add_argument("--force", action="store_true", help="强制执行操作，不提示确认")

    parser.add_argument(
        "--output-format",
        choices=["json", "text", "stream-json"],
        default="text",
        help="指定输出格式（json、text 或 stream-json），默认为 text。stream-json 格式适用于流式传输场景，逐块返回结构化数据",
    )

    parser.add_argument(
        "--stream-partial-output",
        action="store_true",
        default=False,
        help="流式输出部分结果",
    )

    parser.add_argument(
        "--prompt-file",
        type=str,
        help="指定包含任务描述的文件路径（必须是绝对路径）",
    )

    parser.add_argument(
        "task_description", nargs="?", help="任务描述，从命令行接收的任务描述内容"
    )

    return parser.parse_args()


def format_output(data: any, output_format: str) -> str:
    """
    根据指定的格式格式化输出
    """
    import json

    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    elif output_format == "stream-json":
        # stream-json 格式：JSON Lines (JSONL) 格式，每行一个 JSON 对象
        # 适用于流式传输场景，逐块返回结构化数据
        if isinstance(data, (list, tuple)):
            # 如果是列表或元组，每行输出一个 JSON 对象
            return "\n".join(json.dumps(item, ensure_ascii=False) for item in data)
        elif isinstance(data, dict):
            # 如果是字典，直接输出为单行 JSON
            return json.dumps(data, ensure_ascii=False)
        else:
            # 其他类型，包装为字典后输出
            return json.dumps({"data": data}, ensure_ascii=False)
    else:
        return str(data)


def stream_json_output(data: any, flush: bool = True):
    """
    流式输出 JSON 格式数据（JSON Lines 格式）

    符合 JSON Lines (JSONL) 规范：每行一个完整的 JSON 对象，以换行符分隔。
    适用于流式传输场景，逐块返回结构化数据。

    Args:
        data: 要输出的数据
        flush: 是否立即刷新输出缓冲区（默认 True，确保实时输出）

    示例:
        # 输出单个对象
        stream_json_output({'type': 'message', 'content': 'Hello'})
        # 输出: {"type":"message","content":"Hello"}

        # 输出列表（每行一个对象）
        stream_json_output([{'id': 1}, {'id': 2}])
        # 输出:
        # {"id":1}
        # {"id":2}
    """
    import json

    if isinstance(data, (list, tuple)):
        # 列表：逐行输出每个元素
        for item in data:
            json_line = json.dumps(item, ensure_ascii=False)
            print(json_line, flush=flush)
    elif isinstance(data, dict):
        # 字典：输出为单行 JSON
        json_line = json.dumps(data, ensure_ascii=False)
        print(json_line, flush=flush)
    else:
        # 其他类型：包装为字典
        json_line = json.dumps({"data": data}, ensure_ascii=False)
        print(json_line, flush=flush)


async def _stream_agent_execution(
    agent_instance, input_messages, invoke_config, output_format: str, file_writer
):
    """
    流式执行 agent，支持增量流式输出，实时跟踪进度和工具调用状态

    Args:
        agent_instance: agent 实例
        input_messages: 输入消息
        invoke_config: 调用配置
        output_format: 输出格式
        file_writer: 文件写入器
    """
    import json
    import asyncio

    # 在 print 模式下，输出执行开始日志
    if output_format == "stream-json" and file_writer.print_mode:
        stream_json_output({"type": "execution_start", "message": "开始执行 agent"})

    try:
        # 使用 astream_events 来获取详细的事件流，包括工具调用
        accumulated_content = ""
        current_tool_calls = {}
        tool_call_index = 0
        final_response = None  # 用于存储最终结果中的 response 字段

        # 尝试使用 astream_events（如果可用）
        if hasattr(agent_instance, "astream_events"):

            async def process_stream():
                nonlocal accumulated_content, current_tool_calls, tool_call_index, final_response

                try:
                    async for event in agent_instance.astream_events(
                        {"input": input_messages, "index": 0},
                        invoke_config,
                        version="v2",
                    ):
                        event_kind = event.get("event")
                        event_name = event.get("name", "")
                        event_data = event.get("data", {})

                        # 处理工具调用开始事件
                        if event_kind == "on_tool_start":
                            tool_name = event.get("name", "unknown")
                            tool_input = event_data.get("input", {})
                            tool_run_id = event.get("run_id", f"tool_{tool_call_index}")
                            tool_call_index += 1

                            current_tool_calls[tool_run_id] = {
                                "id": tool_run_id,
                                "name": tool_name,
                                "input": tool_input,
                                "status": "running",
                                "start_time": event.get("time", None),
                            }

                        # 处理工具调用结束事件
                        elif event_kind == "on_tool_end":
                            tool_name = event.get("name", "unknown")
                            tool_run_id = event.get("run_id", None)
                            tool_output = event_data.get("output", "")

                            # 更新工具调用状态
                            if tool_run_id and tool_run_id in current_tool_calls:
                                current_tool_calls[tool_run_id]["status"] = "completed"
                                current_tool_calls[tool_run_id]["output"] = tool_output
                                current_tool_calls[tool_run_id]["end_time"] = event.get(
                                    "time", None
                                )
                            else:
                                # 如果没有 run_id，尝试通过名称匹配
                                for run_id, tool_call in current_tool_calls.items():
                                    if (
                                        tool_call["name"] == tool_name
                                        and tool_call["status"] == "running"
                                    ):
                                        tool_call["status"] = "completed"
                                        tool_call["output"] = tool_output
                                        tool_call["end_time"] = event.get("time", None)
                                        break

                        # 处理模型输出事件 - 检查多种可能的事件类型
                        elif event_kind in (
                            "on_chain_stream",
                            "on_chat_model_stream",
                            "on_llm_stream",
                            "on_chat_model_chunk",
                        ):
                            chunk = event_data.get("chunk", {})
                            # 尝试从不同位置提取内容
                            content_to_add = None

                            if isinstance(chunk, dict):
                                # 从 chunk 中提取消息
                                if "messages" in chunk:
                                    for msg in chunk["messages"]:
                                        if hasattr(msg, "content") and msg.content:
                                            content_to_add = msg.content
                                            break
                                # 或者直接从 chunk 中获取 content
                                elif "content" in chunk:
                                    content_to_add = chunk["content"]
                                # 检查是否是 AIMessageChunk
                                elif hasattr(chunk, "content"):
                                    continue
                            elif hasattr(chunk, "content"):
                                content_to_add = chunk.content
                            elif isinstance(chunk, str):
                                content_to_add = chunk

                            if content_to_add:
                                content_str = str(content_to_add)
                                if content_str:  # 只处理非空内容
                                    accumulated_content += content_str

                                    # 在 print 模式下，不输出内容增量日志
                                    if (
                                        output_format == "stream-json"
                                        and file_writer.print_mode
                                    ):
                                        stream_json_output(
                                            {
                                                "type": "content_delta",
                                                "content": content_str,
                                            }
                                        )

                        # 处理链结束事件 - 检查是否包含最终结果
                        elif event_kind == "on_chain_end":
                            # 检查 event_data 中是否包含 response 字段
                            if isinstance(event_data, dict):
                                # 直接检查 response 字段
                                if "response" in event_data:
                                    final_response = event_data.get("response", "")
                                # 或者检查 output 字段中是否包含 response
                                elif "output" in event_data:
                                    output = event_data.get("output", {})
                                    if (
                                        isinstance(output, dict)
                                        and "response" in output
                                    ):
                                        final_response = output.get("response", "")

                            # 在 print 模式下，输出执行进度日志
                            if (
                                output_format == "stream-json"
                                and file_writer.print_mode
                            ):
                                stream_json_output(
                                    {
                                        "type": "execution_progress",
                                        "status": "processing",
                                        "accumulated_content_length": len(
                                            accumulated_content
                                        ),
                                        "tool_calls_count": len(
                                            [
                                                tc
                                                for tc in current_tool_calls.values()
                                                if tc["status"] == "completed"
                                            ]
                                        ),
                                    }
                                )

                        # 处理链开始事件（用于跟踪进度）
                        elif event_kind == "on_chain_start":
                            # 在 print 模式下，输出执行进度日志
                            if (
                                output_format == "stream-json"
                                and file_writer.print_mode
                            ):
                                stream_json_output(
                                    {
                                        "type": "execution_progress",
                                        "status": "started",
                                        "chain_name": event_name,
                                    }
                                )

                except Exception as stream_error:
                    # 如果 astream_events 失败，回退到 astream
                    if output_format == "stream-json" and file_writer.print_mode:
                        stream_json_output(
                            {
                                "type": "warning",
                                "message": f"astream_events 失败，回退到 astream: {stream_error}",
                            }
                        )
                    raise

            # 运行异步流处理
            try:
                await process_stream()
                # 成功执行，输出最终结果（只在 print_mode 下输出）
                if output_format == "stream-json" and file_writer.print_mode:
                    # 优先使用 response 字段，如果没有则使用累积的内容
                    final_content = (
                        final_response
                        if final_response is not None
                        else accumulated_content
                    )
                    result_data = {
                        "type": "execution_complete",
                        "status": "success",
                        "accumulated_content": accumulated_content,
                        "response": final_content,
                    }

                    stream_json_output(result_data)

                return
            except Exception:
                # 如果 astream_events 失败，回退到 astream
                pass

        # 回退到 astream 方法（如果 astream_events 不可用或失败）
        async def process_simple_stream():
            nonlocal accumulated_content, current_tool_calls, tool_call_index, final_response

            async for chunk in agent_instance.astream(
                {"input": input_messages, "index": 0}, invoke_config
            ):
                # 处理字典格式的 chunk
                if isinstance(chunk, dict):
                    # 检查是否包含 response 字段（最终结果）
                    if "response" in chunk:
                        final_response = chunk.get("response", "")

                    # 处理消息
                    if "messages" in chunk:
                        for msg in chunk["messages"]:
                            # 检查是否是工具调用消息
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_call_id = getattr(
                                        tool_call, "id", f"tool_{tool_call_index}"
                                    )
                                    tool_call_index += 1
                                    tool_name = getattr(tool_call, "name", "unknown")
                                    tool_args = getattr(tool_call, "args", {})

                                    current_tool_calls[tool_call_id] = {
                                        "id": tool_call_id,
                                        "name": tool_name,
                                        "input": tool_args,
                                        "status": "running",
                                    }

                                    # 注意：根据需求，在 print_mode 下不输出工具调用日志

                            # 检查是否是工具结果消息
                            elif hasattr(msg, "name") and hasattr(msg, "content"):
                                # 这可能是工具执行结果
                                tool_name = getattr(msg, "name", "unknown")
                                tool_output = getattr(msg, "content", "")

                                # 更新工具调用状态
                                for (
                                    tool_call_id,
                                    tool_call,
                                ) in current_tool_calls.items():
                                    if (
                                        tool_call["name"] == tool_name
                                        and tool_call["status"] == "running"
                                    ):
                                        tool_call["status"] = "completed"
                                        tool_call["output"] = tool_output
                                        break

                            # 处理普通消息内容（增量输出）
                            elif hasattr(msg, "content") and msg.content:
                                content = str(msg.content)
                                if content:  # 只处理非空内容
                                    accumulated_content += content

                                    # 在 print 模式下，输出内容增量日志
                                    if (
                                        output_format == "stream-json"
                                        and file_writer.print_mode
                                    ):
                                        stream_json_output(
                                            {
                                                "type": "content_delta",
                                                "content": content,
                                            }
                                        )

                # 处理其他格式的 chunk（如直接的消息对象）
                elif hasattr(chunk, "content") and chunk.content:
                    content = str(chunk.content)
                    if content:
                        accumulated_content += content
                        # 在 print 模式下，不输出内容增量日志
                        if output_format == "stream-json" and file_writer.print_mode:
                            stream_json_output(
                                {"type": "content_delta", "content": content}
                            )

        await process_simple_stream()

        # 输出最终结果（只在 print_mode 下输出）
        if output_format == "stream-json" and file_writer.print_mode:
            # 优先使用 response 字段，如果没有则使用累积的内容
            final_content = (
                final_response if final_response is not None else accumulated_content
            )
            result_data = {
                "type": "execution_complete",
                "status": "success",
                "accumulated_content": accumulated_content,
                "response": final_content,
            }

            stream_json_output(result_data)

    except Exception as e:
        if output_format == "stream-json" and file_writer.print_mode:
            stream_json_output(
                {
                    "type": "execution_error",
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
        else:
            print(f"\n 执行过程中发生错误: {e}")
            traceback.print_exc()


async def _invoke_agent_execution(
    agent_instance, input_messages, invoke_config, output_format: str, file_writer
):
    """
    text格式或json格式输出执行结果

    Args:
        agent_instance: agent 实例
        input_messages: 输入消息
        invoke_config: 调用配置
        output_format: 输出格式
        file_writer: 文件写入器
    """
    import json

    try:
        # 同步调用
        result = await agent_instance.ainvoke(
            {"input": input_messages, "index": 0}, invoke_config
        )

        # 提取结果内容
        output_content = ""

        if isinstance(result, dict):
            output_content = result.get("response", "")

        # 在 print_mode 下才输出结果（text/json 格式只输出结果）
        if file_writer.print_mode:
            if output_format == "json":
                result_data = {"content": output_content}
                print("\n 执行结果:")
                print(format_output(result_data, output_format))
            elif output_format == "text":
                print("\n 执行结果:")
                if output_content:
                    print(output_content)

    except Exception as e:
        if output_format == "stream-json" and file_writer.print_mode:
            stream_json_output(
                {
                    "type": "execution_error",
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
        elif file_writer.print_mode:
            # text/json 格式的错误信息只在 print_mode 下输出
            print(f"\n 执行过程中发生错误: {e}")
            traceback.print_exc()


async def main():
    """
    主函数：程序入口点
    """
    # 解析命令行参数
    args = parse_arguments()

    # 获取脚本所在目录（用于内部文件，如 todos.json）
    script_dir = Path(__file__).parent.resolve()
    
    # 获取当前工作目录（用户要分析的目标目录）
    working_dir = Path.cwd().resolve()

    # 检查并删除已存在的 todos.json 文件（使用脚本目录）
    todos_file = script_dir / "data" / "todos.json"
    if todos_file.exists():
        try:
            todos_file.unlink()
        except Exception as e:
            print(f"警告: 无法删除 {todos_file}: {e}")

    # 创建安全的文件写入器
    # print_mode 控制是否打印输出，force 控制是否强制写入文件
    # 两者可以同时生效：使用 --force 时既能打印输出，又能写入文件
    print_mode = args.print
    file_writer = SafeFileWriter(print_mode, working_dir, args.force)

    # 将 file_writer 存储到线程本地存储中，以便中间件和工具函数可以访问
    set_file_writer(file_writer)

    # 根据参数输出信息
    if args.output_format == "stream-json":
        # stream-json 格式：输出启动信息为 JSON 对象
        stream_json_output(
            {
                "type": "startup",
                "message": "Execute Agent 正在启动",
                "print_mode": args.print,
                "force": args.force,
                "stream_partial_output": args.stream_partial_output,
                "current_dir": working_dir.as_posix(),
                "output_format": args.output_format,
            }
        )

    try:
        # 按需初始化 agent
        agent_instance = await agent.initialize_graph()

        if args.output_format == "stream-json":
            stream_json_output(
                {
                    "type": "status",
                    "status": "success",
                    "message": "Execute Agent 启动成功",
                }
            )

        # 将参数传递给 agent（如果需要）
        # 这里可以根据实际需求将 args 传递给 agent
        agent_config = {
            "print_mode": args.print,
            "force": args.force,
            "output_format": args.output_format,
            "stream_partial_output": args.stream_partial_output,
            "file_writer": file_writer,
            "current_dir": working_dir,
        }

        # 输出配置信息（根据输出格式）
        config_data = {
            "mode": "print" if print_mode else "normal",
            "force": args.force,
            "output_format": args.output_format,
            "stream_partial_output": args.stream_partial_output,
            "current_dir": working_dir.as_posix(),
        }

        if args.output_format == "stream-json":
            # stream-json 格式：直接流式输出，不添加额外文本
            stream_json_output({"type": "config", **config_data})

        # 调用 agent 的主要功能方法
        # 优先级和互斥检查：不能同时使用 --prompt-file 与 --prompt 或 task_description
        import sys

        # 检查互斥条件
        prompt_sources = []
        if args.prompt_file:
            prompt_sources.append("--prompt-file")
        if args.prompt:
            prompt_sources.append("--prompt")
        if args.task_description:
            prompt_sources.append("task_description (位置参数)")

        if len(prompt_sources) > 1:
            error_msg = f"错误: 不能同时使用多个提示词来源: {', '.join(prompt_sources)}。请只使用其中一个。"
            if args.output_format == "stream-json":
                stream_json_output(
                    {
                        "type": "error",
                        "status": "invalid_input",
                        "message": error_msg,
                    }
                )
            else:
                print(error_msg)
            return

        # 处理 --prompt-file 参数
        if args.prompt_file:
            prompt_file_path = Path(args.prompt_file)

            # 验证是否为绝对路径
            if not prompt_file_path.is_absolute():
                error_msg = f"错误: --prompt-file 参数必须是绝对路径，当前值: {args.prompt_file}"
                if args.output_format == "stream-json":
                    stream_json_output(
                        {
                            "type": "error",
                            "status": "invalid_path",
                            "message": error_msg,
                        }
                    )
                else:
                    print(error_msg)
                return

            # 验证文件是否存在
            if not prompt_file_path.exists():
                error_msg = f"错误: 找不到指定的提示词文件: {args.prompt_file}"
                if args.output_format == "stream-json":
                    stream_json_output(
                        {
                            "type": "error",
                            "status": "file_not_found",
                            "message": error_msg,
                        }
                    )
                else:
                    print(error_msg)
                return

            # 读取文件内容
            try:
                with open(prompt_file_path, "r", encoding="utf-8") as f:
                    user_message = f.read().strip()
            except Exception as e:
                error_msg = f"错误: 无法读取提示词文件 {args.prompt_file}: {e}"
                if args.output_format == "stream-json":
                    stream_json_output(
                        {
                            "type": "error",
                            "status": "read_error",
                            "message": error_msg,
                        }
                    )
                else:
                    print(error_msg)
                return

            # 读取成功后，立即删除 prompt-file
            try:
                if prompt_file_path.exists():
                    prompt_file_path.unlink()
            except Exception as e:
                # 删除失败时给出警告，但不影响程序运行
                warning_msg = f"警告: 无法删除提示词文件 {args.prompt_file}: {e}"
                if args.output_format == "stream-json":
                    stream_json_output(
                        {
                            "type": "warning",
                            "message": warning_msg,
                        }
                    )
                else:
                    print(warning_msg)

        # 如果提供了 --prompt 参数，直接使用它
        elif args.prompt:
            user_message = args.prompt.strip()
        # 否则使用位置参数
        elif args.task_description:
            user_message = args.task_description.strip()
        else:
            user_message = None

        # 使用 path_parser 处理包含 @ 的路径引用
        if user_message:
            user_message = process_at_paths(user_message)

        if not user_message:
            if args.output_format == "stream-json":
                stream_json_output(
                    {
                        "type": "error",
                        "status": "no_input",
                        "message": "未检测到用户输入的提示词，请使用 --prompt-file、--prompt 参数或位置参数提供任务描述",
                    }
                )
            else:
                print(
                    "未检测到用户输入的提示词，请使用 --prompt-file、--prompt 参数或位置参数提供任务描述"
                )
            return

        # 生成唯一的线程 ID
        import uuid

        thread_id = str(uuid.uuid4())

        # 获取 RECURSION_LIMIT 配置
        recursion_limit = config.get("RECURSION_LIMIT", 1000)

        # 准备调用配置
        invoke_config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": recursion_limit,
        }

        # 准备输入消息
        input_messages = {"messages": [("user", user_message)]}

        # 根据是否启用流式输出选择调用方式
        if args.stream_partial_output or args.output_format == "stream-json":
            # 流式输出模式
            await _stream_agent_execution(
                agent_instance=agent_instance,
                input_messages=input_messages,
                invoke_config=invoke_config,
                output_format=args.output_format,
                file_writer=file_writer,
            )
        else:
            # 非流式输出模式
            await _invoke_agent_execution(
                agent_instance=agent_instance,
                input_messages=input_messages,
                invoke_config=invoke_config,
                output_format=args.output_format,
                file_writer=file_writer,
            )

    except KeyboardInterrupt:
        if args.output_format == "stream-json" and args.print:
            stream_json_output(
                {"type": "error", "status": "interrupted", "message": "用户中断程序"}
            )
        elif not args.print:
            print("\n  用户中断程序")
        sys.exit(0)
    except Exception as e:
        if args.output_format == "stream-json" and args.print:
            stream_json_output(
                {
                    "type": "error",
                    "status": "exception",
                    "message": "程序执行时发生异常",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
        elif args.print:
            print(f"\n 错误: 程序执行时发生异常")
            print(f"   详细信息: {e}")
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
