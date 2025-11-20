#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具注册表模块
负责初始化和提供所有可用工具
"""

import asyncio
import logging
from typing import List, Any

logger = logging.getLogger(__name__)


async def get_execute_tools() -> List[Any]:
    """
    获取所有可用工具的列表

    Returns:
        List[Any]: 工具列表，包含内置工具和从 MCP 客户端获取的工具
    """
    # 在函数内部导入工具，避免顶层循环导入
    from tools import (
        read_file,
        write_file_tool,
        edit_file,
        codebase_search,
        list_directory,
        search_files,
        grep,
        run_terminal_cmd,
        read_lints,
        delete_file,
        web_search,
        get_mcp_clients,
    )

    # 基础工具列表
    tools = [
        read_file,
        write_file_tool,
        edit_file,
        codebase_search,
        list_directory,
        search_files,
        grep,
        run_terminal_cmd,
        read_lints,
        delete_file,
        web_search,
    ]

    try:
        # 初始化 MCP 客户端
        langchain_mcp_client, context7_mcp_client = get_mcp_clients()

        # 并发获取 MCP 工具
        async_tasks = [
            langchain_mcp_client.get_tools(),
            context7_mcp_client.get_tools(),
        ]
        mcp_tool_lists = await asyncio.gather(*async_tasks)

        # 合并 MCP 工具
        for mcp_tools in mcp_tool_lists:
            tools.extend(mcp_tools)

    except Exception as e:
        # 如果 MCP 客户端初始化失败，记录警告但继续使用基础工具
        print(f"警告: MCP 客户端初始化失败，仅使用基础工具: {e}")

    return tools
