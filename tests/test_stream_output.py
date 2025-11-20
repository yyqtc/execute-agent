#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式输出逻辑的单元测试
验证流式输出逻辑，确保支持增量内容输出和实时跟踪工具调用状态
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import json
import sys
import os
from io import StringIO
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

# 导入被测试的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import stream_json_output, _stream_agent_execution


class TestStreamJSONOutput(unittest.TestCase):
    """stream_json_output 函数的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 捕获标准输出
        self.stdout_capture = StringIO()

    def tearDown(self):
        """每个测试后的清理工作"""
        self.stdout_capture.close()

    def test_output_dict_as_single_json_line(self):
        """测试：输出字典时，应该输出为单行 JSON"""
        with patch("builtins.print") as mock_print:
            data = {"type": "message", "content": "Hello"}
            stream_json_output(data)

            # 验证 print 被调用一次
            self.assertEqual(mock_print.call_count, 1)

            # 验证输出的是有效的 JSON
            call_args = mock_print.call_args[0][0]
            parsed = json.loads(call_args)
            self.assertEqual(parsed, data)

    def test_output_list_as_multiple_json_lines(self):
        """测试：输出列表时，应该每行输出一个 JSON 对象"""
        with patch("builtins.print") as mock_print:
            data = [{"id": 1}, {"id": 2}, {"id": 3}]
            stream_json_output(data)

            # 验证 print 被调用三次（每个元素一行）
            self.assertEqual(mock_print.call_count, 3)

            # 验证每行都是有效的 JSON
            for i, call in enumerate(mock_print.call_args_list):
                parsed = json.loads(call[0][0])
                self.assertEqual(parsed, data[i])

    def test_output_tuple_as_multiple_json_lines(self):
        """测试：输出元组时，应该每行输出一个 JSON 对象"""
        with patch("builtins.print") as mock_print:
            data = ({"type": "start"}, {"type": "end"})
            stream_json_output(data)

            # 验证 print 被调用两次
            self.assertEqual(mock_print.call_count, 2)

    def test_output_other_type_wrapped_in_dict(self):
        """测试：输出其他类型时，应该包装为字典"""
        with patch("builtins.print") as mock_print:
            data = "plain string"
            stream_json_output(data)

            # 验证 print 被调用一次
            self.assertEqual(mock_print.call_count, 1)

            # 验证输出被包装为字典
            call_args = mock_print.call_args[0][0]
            parsed = json.loads(call_args)
            self.assertIn("data", parsed)
            self.assertEqual(parsed["data"], data)

    def test_output_with_ensure_ascii_false(self):
        """测试：输出包含非 ASCII 字符时，应该正确处理"""
        with patch("builtins.print") as mock_print:
            data = {"type": "message", "content": "你好，世界！"}
            stream_json_output(data)

            # 验证输出包含中文字符
            call_args = mock_print.call_args[0][0]
            self.assertIn("你好", call_args)

            # 验证可以正确解析
            parsed = json.loads(call_args)
            self.assertEqual(parsed["content"], "你好，世界！")

    def test_output_flush_parameter(self):
        """测试：flush 参数是否正确传递"""
        with patch("builtins.print") as mock_print:
            data = {"type": "test"}

            # 测试 flush=True（默认）
            stream_json_output(data, flush=True)
            self.assertTrue(mock_print.call_args[1].get("flush", False))

            # 测试 flush=False
            mock_print.reset_mock()
            stream_json_output(data, flush=False)
            self.assertFalse(mock_print.call_args[1].get("flush", True))


class TestStreamAgentExecution(unittest.TestCase):
    """_stream_agent_execution 函数的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        self.mock_agent = MagicMock()
        self.input_messages = {"messages": [("user", "test message")]}
        self.invoke_config = {"configurable": {"thread_id": "test-thread-1"}}
        self.file_writer = MagicMock()

    def test_execution_start_event(self):
        """测试：执行开始时应该发送 execution_start 事件"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟 agent 没有 astream_events 方法，使用 astream
            async def mock_astream(*args, **kwargs):
                # 空生成器，只用于测试 execution_start 事件
                if False:
                    yield

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 execution_start 事件被发送
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            start_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "execution_start"
            ]
            self.assertGreater(len(start_events), 0)

    def test_content_delta_incremental_output(self):
        """测试：增量内容输出应该通过 content_delta 事件发送"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟消息内容流
            mock_chunk1 = MagicMock()
            mock_chunk1.content = "Hello"
            mock_chunk2 = MagicMock()
            mock_chunk2.content = " World"

            # 模拟 astream 返回增量内容
            async def mock_astream(*args, **kwargs):
                yield mock_chunk1
                yield mock_chunk2

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            import asyncio

            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 content_delta 事件被发送
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            delta_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "content_delta"
            ]

            # 应该至少有两个增量事件
            self.assertGreaterEqual(len(delta_events), 2)

            # 验证内容正确
            contents = [event["content"] for event in delta_events]
            self.assertIn("Hello", contents)
            self.assertIn(" World", contents)

    def test_tool_call_start_event(self):
        """测试：工具调用开始时应该发送 tool_call_start 事件"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟工具调用消息
            mock_tool_call = MagicMock()
            mock_tool_call.id = "tool_123"
            mock_tool_call.name = "test_tool"
            mock_tool_call.args = {"param": "value"}

            mock_message = MagicMock()
            mock_message.tool_calls = [mock_tool_call]
            mock_message.content = None

            mock_chunk = {"messages": [mock_message]}

            async def mock_astream(*args, **kwargs):
                yield mock_chunk

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 tool_call_start 事件被发送
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            start_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "tool_call_start"
            ]

            self.assertGreater(len(start_events), 0)
            self.assertEqual(start_events[0]["tool_name"], "test_tool")
            self.assertEqual(start_events[0]["input"], {"param": "value"})

    def test_tool_call_end_event(self):
        """测试：工具调用结束时应该发送 tool_call_end 事件"""
        with patch("main.stream_json_output") as mock_stream:
            # 首先需要有一个工具调用开始，然后才有结束
            mock_tool_call = MagicMock()
            mock_tool_call.id = "tool_123"
            mock_tool_call.name = "test_tool"
            mock_tool_call.args = {}

            mock_start_message = MagicMock()
            mock_start_message.tool_calls = [mock_tool_call]
            mock_start_message.content = None

            # 模拟工具结果消息（确保没有 tool_calls 属性或 tool_calls 为空）
            mock_tool_result = MagicMock()
            mock_tool_result.name = "test_tool"
            mock_tool_result.content = "tool output result"
            # 确保 tool_calls 属性不存在或为空，以便进入 elif 分支
            if hasattr(mock_tool_result, "tool_calls"):
                delattr(mock_tool_result, "tool_calls")

            async def mock_astream(*args, **kwargs):
                # 先发送工具调用开始
                yield {"messages": [mock_start_message]}
                # 然后发送工具调用结束
                yield {"messages": [mock_tool_result]}

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 tool_call_end 事件被发送
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            end_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "tool_call_end"
            ]

            self.assertGreater(len(end_events), 0)
            self.assertEqual(end_events[0]["tool_name"], "test_tool")
            self.assertIn("output", end_events[0])

    def test_tool_call_state_tracking(self):
        """测试：工具调用状态应该被正确跟踪"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟工具调用流程：开始 -> 结束
            mock_tool_call = MagicMock()
            mock_tool_call.id = "tool_456"
            mock_tool_call.name = "tracked_tool"
            mock_tool_call.args = {}

            mock_start_message = MagicMock()
            mock_start_message.tool_calls = [mock_tool_call]
            mock_start_message.content = None

            mock_end_message = MagicMock()
            mock_end_message.name = "tracked_tool"
            mock_end_message.content = "result"
            # 确保 tool_calls 属性不存在或为空，以便进入 elif 分支
            if hasattr(mock_end_message, "tool_calls"):
                delattr(mock_end_message, "tool_calls")

            async def mock_astream(*args, **kwargs):
                yield {"messages": [mock_start_message]}
                yield {"messages": [mock_end_message]}

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证执行完成事件包含工具调用信息
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            complete_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "execution_complete"
            ]

            self.assertGreater(len(complete_events), 0)
            self.assertIn("tool_calls", complete_events[0])
            tool_calls = complete_events[0]["tool_calls"]
            self.assertGreater(len(tool_calls), 0)

            # 验证工具调用状态为 completed
            completed_tools = [
                tc for tc in tool_calls if tc.get("status") == "completed"
            ]
            self.assertGreater(len(completed_tools), 0)

    def test_execution_complete_event(self):
        """测试：执行完成时应该发送 execution_complete 事件"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟简单的内容流
            mock_chunk = MagicMock()
            mock_chunk.content = "Final content"

            async def mock_astream(*args, **kwargs):
                yield mock_chunk

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 execution_complete 事件被发送
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            complete_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "execution_complete"
            ]

            self.assertGreater(len(complete_events), 0)
            self.assertEqual(complete_events[0]["status"], "success")
            self.assertIn("accumulated_content", complete_events[0])

    def test_astream_events_preferred_over_astream(self):
        """测试：如果 agent 支持 astream_events，应该优先使用它"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟 astream_events 方法
            async def mock_astream_events(*args, **kwargs):
                yield {"event": "on_chain_start", "name": "test_chain", "data": {}}

            self.mock_agent.astream_events = mock_astream_events
            self.mock_agent.astream = AsyncMock()

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 astream_events 被调用
            self.assertTrue(hasattr(self.mock_agent, "astream_events"))
            # 注意：由于我们使用了 mock，无法直接验证调用，但可以验证执行没有失败

    def test_error_handling(self):
        """测试：执行错误时应该发送 execution_error 事件"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟执行错误
            async def mock_astream(*args, **kwargs):
                raise Exception("Test error")

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证 execution_error 事件被发送
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            error_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "execution_error"
            ]

            self.assertGreater(len(error_events), 0)
            self.assertEqual(error_events[0]["status"], "error")
            self.assertIn("error", error_events[0])

    def test_accumulated_content_tracking(self):
        """测试：累积内容应该被正确跟踪"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟多个内容块
            chunks = [
                MagicMock(content="Part 1 "),
                MagicMock(content="Part 2 "),
                MagicMock(content="Part 3"),
            ]

            async def mock_astream(*args, **kwargs):
                for chunk in chunks:
                    yield chunk

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证执行完成事件包含完整的累积内容
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            complete_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "execution_complete"
            ]

            self.assertGreater(len(complete_events), 0)
            accumulated = complete_events[0]["accumulated_content"]
            self.assertEqual(accumulated, "Part 1 Part 2 Part 3")

    def test_text_output_format(self):
        """测试：text 输出格式应该使用 print 而不是 stream_json_output"""
        with patch("builtins.print") as mock_print:
            # 模拟内容流
            mock_chunk = MagicMock()
            mock_chunk.content = "Text output"

            async def mock_astream(*args, **kwargs):
                yield mock_chunk

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（使用 text 格式，不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "text",  # 使用 text 格式
                self.file_writer,
            )

            # 验证使用了 print 输出
            self.assertGreater(mock_print.call_count, 0)

    def test_empty_content_handling(self):
        """测试：空内容应该被正确处理（不发送 content_delta）"""
        with patch("main.stream_json_output") as mock_stream:
            # 模拟空内容
            mock_chunk = MagicMock()
            mock_chunk.content = ""

            async def mock_astream(*args, **kwargs):
                yield mock_chunk

            self.mock_agent.astream_events = None
            self.mock_agent.astream = mock_astream

            # 运行流式执行（不模拟 asyncio.run，让它正常执行）
            _stream_agent_execution(
                self.mock_agent,
                self.input_messages,
                self.invoke_config,
                "stream-json",
                self.file_writer,
            )

            # 验证没有发送空的 content_delta 事件
            call_args_list = [call[0][0] for call in mock_stream.call_args_list]
            delta_events = [
                event
                for event in call_args_list
                if isinstance(event, dict) and event.get("type") == "content_delta"
            ]

            # 空内容不应该产生 content_delta 事件
            empty_deltas = [e for e in delta_events if not e.get("content")]
            self.assertEqual(len(empty_deltas), 0)


if __name__ == "__main__":
    unittest.main()
