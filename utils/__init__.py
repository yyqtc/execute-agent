"""
Utils package initialization module.

This module provides utility classes and functions used by the tools package.
All file operations should be accessed through the tools package for automatic lock management.
"""

# Import from file_lock module
from .file_lock import (
    FileAccessManager,
    get_file_manager,
    reset_file_manager,
)

# Import from command_parser module
from .command_parser import CommandFileAnalyzer

# Note: file_operations 不在此导出，应该通过 tools 包访问
# 这样可以确保使用智能锁管理版本

# Define __all__ to explicitly declare public API
__all__ = [
    # File lock module exports
    "FileAccessManager",
    "get_file_manager",
    "reset_file_manager",
    # Command parser module exports
    "CommandFileAnalyzer",
]
