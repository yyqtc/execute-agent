"""
Tools package initialization module.

This module provides a unified interface for all tool modules in the tools package.
All public classes and functions are exported through this module.
"""

# Import from command module
from .command import (
    run_terminal_cmd,
    DANGEROUS_COMMANDS,
    COMMAND_WHITELIST,
    CRITICAL_PATH_BLACKLIST,
    ALLOWED_DELETE_DIRECTORIES,
)

# Import from lint module
from .lint import read_lints

# Import from search module
from .search import search_files, grep, codebase_search

# Import from file_operations_with_lock module (智能锁管理版本)
from .file_operations_with_lock import (
    read_file,
    write_file,
    write_file_tool,
    edit_file,
    delete_file,
    list_directory,
    set_task_context,
    clear_task_context,
    get_task_context,
)

# Import format_error from utils (工具函数)
from utils.file_operations import format_error

# Import from mcp module
from .mcp import (
    create_langchain_mcp_client,
    create_context7_mcp_client,
    get_mcp_clients,
)

# Import from network module
from .network import web_search

# Import from gitignore module
from .gitignore import (
    load_gitignore_patterns,
    is_path_ignored,
    get_project_root,
)

# Import from config module
from .config import get_config

# Import from utils.file_lock module
from utils.file_lock import (
    FileAccessManager,
    get_file_manager,
    reset_file_manager,
)

# Import from utils.command_parser module
from utils.command_parser import CommandFileAnalyzer

# Define __all__ to explicitly declare public API
__all__ = [
    # Command module exports
    "run_terminal_cmd",
    "DANGEROUS_COMMANDS",
    "COMMAND_WHITELIST",
    "CRITICAL_PATH_BLACKLIST",
    "ALLOWED_DELETE_DIRECTORIES",
    # Lint module exports
    "read_lints",
    # Search module exports
    "search_files",
    "grep",
    "codebase_search",
    # File operations module exports
    "read_file",
    "write_file",
    "write_file_tool",
    "edit_file",
    "delete_file",
    "list_directory",
    "format_error",
    "set_task_context",
    "clear_task_context",
    "get_task_context",
    # MCP module exports
    "create_langchain_mcp_client",
    "create_context7_mcp_client",
    "get_mcp_clients",
    # Network module exports
    "web_search",
    # Gitignore module exports
    "load_gitignore_patterns",
    "is_path_ignored",
    "get_project_root",
    # Config module exports
    "get_config",
    # File lock module exports
    "FileAccessManager",
    "get_file_manager",
    "reset_file_manager",
    # Command parser module exports
    "CommandFileAnalyzer",
]
