from tools.file_operations_with_lock import (
    read_file as read_file_impl,
    write_file as write_file_impl,
    edit_file as edit_file_impl,
    delete_file as delete_file_impl,
    list_directory as list_directory_impl,
    set_task_context as set_task_context_impl,
    clear_task_context as clear_task_context_impl,
    get_task_context as get_task_context_impl,
)

from utils.file_lock import FileAccessManager

from typing import Optional

def read_file(
    file_path: str,
    encoding: str = "utf-8",
    chunk_size: int = 8192,
    stream: bool = False,
):
    """
    智能文件读取（自动锁管理）
    
    单任务执行时：无锁，高性能
    并行执行时：自动使用读锁，允许多个任务同时读取
    
    Args:
        file_path: 文件路径
        encoding: 文件编码
        chunk_size: 流式读取时的块大小
        stream: 是否流式读取
        
    Returns:
        文件内容或错误消息
    """

    return read_file_impl(file_path, encoding, chunk_size, stream)

def write_file(
    file_path: str,
    content: str,
    file_writer: Optional[object] = None,
    overwrite: bool = True,
) -> str:
    """
    overwrite为True时，智能文件覆盖写入；overwrite为False时，智能文件追加写入（自动锁管理）
    
    单任务执行时：无锁，高性能
    并行执行时：自动使用写锁，独占访问
    
    Args:
        file_path: 文件路径
        content: 要写入的内容
        file_writer: SafeFileWriter实例（可选）
        overwrite: 是否覆盖文件（默认不覆盖）
        
    Returns:
        操作结果消息
    """

    return write_file_impl(file_path, content, file_writer, overwrite)

def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False
) -> str:
    """
    智能文件编辑（自动锁管理）
    
    单任务执行时：无锁，高性能
    并行执行时：自动使用写锁，独占访问
    
    Args:
        file_path: 文件路径
        old_string: 要替换的字符串
        new_string: 新字符串
        replace_all: 是否替换所有匹配项
        
    Returns:
        操作结果消息
    """

    return edit_file_impl(file_path, old_string, new_string, replace_all)

def delete_file(file_path: str) -> str:
    """
    智能文件删除（自动锁管理）
    
    单任务执行时：无锁，高性能
    并行执行时：自动使用写锁，独占访问
    
    Args:
        file_path: 文件路径
        
    Returns:
        操作结果消息
    """

    return delete_file_impl(file_path)

def list_directory(directory_path: str = ".", recursive: bool = False) -> list:
    """
    列出目录内容（只读操作，无需锁）
    
    Args:
        directory_path: 目录路径
        recursive: 是否递归列出
        
    Returns:
        目录内容列表
    """

    return list_directory_impl(directory_path, recursive)

def set_task_context(task_id: str, manager: Optional[FileAccessManager] = None):
    """
    设置当前任务上下文（启用锁机制）
    
    Args:
        task_id: 任务ID
        manager: 文件访问管理器，None表示使用全局管理器
    """

    return set_task_context_impl(task_id, manager)

def clear_task_context():
    """清除任务上下文（禁用锁机制）"""

    return clear_task_context_impl()

def get_task_context() -> tuple:
    """
    获取当前任务上下文
    
    Returns:
        (task_id, manager, lock_enabled)
    """
    
    return get_task_context_impl()
