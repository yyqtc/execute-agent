"""
智能文件操作工具（自动锁管理）

这个模块提供了支持智能锁管理的文件操作工具：
- 单任务执行时：无锁，高性能
- 并行执行时：自动加锁，防止冲突

所有函数都是同步的，向后兼容现有代码。
"""

import logging
import asyncio
from typing import Optional
from threading import local as ThreadLocal

# 尝试导入 nest_asyncio 以支持嵌套事件循环
try:
    import nest_asyncio
    nest_asyncio.apply()
    _nest_asyncio_available = True
except ImportError:
    _nest_asyncio_available = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "nest_asyncio 未安装，可能在异步环境中调用同步文件操作会失败。"
        "建议安装: pip install nest-asyncio"
    )

from utils.file_operations import (
    read_file as _read_file_impl,
    write_file as _write_file_impl,
    edit_file as _edit_file_impl,
    delete_file as _delete_file_impl,
    list_directory as _list_directory_impl,
    format_error,
)
from utils.file_lock import FileAccessManager, get_file_manager

logger = logging.getLogger(__name__)

# 线程本地存储（用于传递任务上下文）
_thread_local = ThreadLocal()


def set_task_context(task_id: str, manager: Optional[FileAccessManager] = None):
    """
    设置当前任务上下文（启用锁机制）
    
    Args:
        task_id: 任务ID
        manager: 文件访问管理器，None表示使用全局管理器
    """
    _thread_local.task_id = task_id
    _thread_local.manager = manager or get_file_manager()
    _thread_local.lock_enabled = True
    logger.debug(f"[任务上下文] 启用锁机制: {task_id}")


def clear_task_context():
    """清除任务上下文（禁用锁机制）"""
    task_id = getattr(_thread_local, 'task_id', None)
    _thread_local.task_id = None
    _thread_local.manager = None
    _thread_local.lock_enabled = False
    if task_id:
        logger.debug(f"[任务上下文] 清除: {task_id}")


def get_task_context() -> tuple:
    """
    获取当前任务上下文
    
    Returns:
        (task_id, manager, lock_enabled)
    """
    return (
        getattr(_thread_local, 'task_id', None),
        getattr(_thread_local, 'manager', None),
        getattr(_thread_local, 'lock_enabled', False),
    )


def _run_with_lock(coro):
    """
    在事件循环中运行协程（同步包装）
    
    支持在已运行的事件循环中调用（通过 nest_asyncio）
    
    Args:
        coro: 协程对象
        
    Returns:
        协程的返回值
    """
    try:
        # 尝试获取当前正在运行的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果有 nest_asyncio，可以在运行的循环中嵌套调用
            if _nest_asyncio_available:
                return loop.run_until_complete(coro)
            else:
                # 没有 nest_asyncio，无法在运行的循环中调用
                raise RuntimeError(
                    "检测到事件循环正在运行，但 nest_asyncio 未安装。"
                    "请安装: pip install nest-asyncio"
                )
        except RuntimeError:
            # 没有正在运行的循环，创建新的
            pass
        
        # 获取或创建事件循环
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
        
    except Exception as e:
        logger.error(f"运行协程时发生错误: {e}")
        raise


async def _read_file_async_with_lock(
    file_path: str,
    task_id: str,
    manager: FileAccessManager,
    encoding: str = "utf-8",
    chunk_size: int = 8192,
    stream: bool = False,
    lock_timeout: float = 5.0
):
    """异步读取文件（带锁，在线程池中执行I/O避免阻塞事件循环）"""
    async with manager.read_lock(file_path, task_id, timeout=lock_timeout):
        # 使用 asyncio.to_thread 在线程池中执行同步 I/O，避免阻塞事件循环
        # 锁会在整个操作期间持有，直到退出 async with 块
        return await asyncio.to_thread(
            _read_file_impl, file_path, encoding, chunk_size, stream
        )


async def _write_file_async_with_lock(
    file_path: str,
    content: str,
    task_id: str,
    manager: FileAccessManager,
    file_writer: Optional[object] = None,
    lock_timeout: float = 10.0
):
    """异步写入文件（带锁，在线程池中执行I/O避免阻塞事件循环）"""
    async with manager.write_lock(file_path, task_id, timeout=lock_timeout):
        return await asyncio.to_thread(
            _write_file_impl, file_path, content, file_writer
        )


async def _edit_file_async_with_lock(
    file_path: str,
    old_string: str,
    new_string: str,
    task_id: str,
    manager: FileAccessManager,
    replace_all: bool = False,
    lock_timeout: float = 10.0
):
    """异步编辑文件（带锁，在线程池中执行I/O避免阻塞事件循环）"""
    async with manager.write_lock(file_path, task_id, timeout=lock_timeout):
        return await asyncio.to_thread(
            _edit_file_impl, file_path, old_string, new_string, replace_all
        )


async def _delete_file_async_with_lock(
    file_path: str,
    task_id: str,
    manager: FileAccessManager,
    lock_timeout: float = 5.0
):
    """异步删除文件（带锁，在线程池中执行I/O避免阻塞事件循环）"""
    async with manager.write_lock(file_path, task_id, timeout=lock_timeout):
        return await asyncio.to_thread(_delete_file_impl, file_path)


# ==================== 公共接口（同步函数） ====================

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
    task_id, manager, lock_enabled = get_task_context()
    
    # 无锁快速路径
    if not lock_enabled or manager is None:
        return _read_file_impl(file_path, encoding, chunk_size, stream)
    
    # 带锁路径
    logger.debug(f"[读锁] {task_id} 准备读取: {file_path}")
    try:
        result = _run_with_lock(
            _read_file_async_with_lock(
                file_path, task_id, manager, encoding, chunk_size, stream
            )
        )
        logger.debug(f"[读锁] {task_id} 完成读取: {file_path}")
        return result
    except TimeoutError as e:
        logger.warning(f"[读锁] {task_id} 超时: {file_path} - {e}")
        return format_error(f"读取文件超时", details=str(e), path=file_path)
    except Exception as e:
        logger.error(f"[读锁] {task_id} 异常: {file_path} - {e}")
        return format_error(f"读取文件失败", details=str(e), path=file_path)


def write_file(
    file_path: str,
    content: str,
    file_writer: Optional[object] = None
) -> str:
    """
    智能文件写入（自动锁管理）
    
    单任务执行时：无锁，高性能
    并行执行时：自动使用写锁，独占访问
    
    Args:
        file_path: 文件路径
        content: 要写入的内容
        file_writer: SafeFileWriter实例（可选）
        
    Returns:
        操作结果消息
    """
    task_id, manager, lock_enabled = get_task_context()
    
    # 无锁快速路径
    if not lock_enabled or manager is None:
        return _write_file_impl(file_path, content, file_writer)
    
    # 带锁路径
    logger.debug(f"[写锁] {task_id} 准备写入: {file_path}")
    try:
        result = _run_with_lock(
            _write_file_async_with_lock(
                file_path, content, task_id, manager, file_writer
            )
        )
        logger.debug(f"[写锁] {task_id} 完成写入: {file_path}")
        return result
    except TimeoutError as e:
        logger.error(f"[写锁] {task_id} 超时: {file_path} - {e}")
        return format_error(f"写入文件超时", details=str(e), path=file_path)
    except Exception as e:
        logger.error(f"[写锁] {task_id} 异常: {file_path} - {e}")
        return format_error(f"写入文件失败", details=str(e), path=file_path)


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
    task_id, manager, lock_enabled = get_task_context()
    
    # 无锁快速路径
    if not lock_enabled or manager is None:
        return _edit_file_impl(file_path, old_string, new_string, replace_all)
    
    # 带锁路径
    logger.debug(f"[写锁] {task_id} 准备编辑: {file_path}")
    try:
        result = _run_with_lock(
            _edit_file_async_with_lock(
                file_path, old_string, new_string, task_id, manager, replace_all
            )
        )
        logger.debug(f"[写锁] {task_id} 完成编辑: {file_path}")
        return result
    except TimeoutError as e:
        logger.error(f"[写锁] {task_id} 超时: {file_path} - {e}")
        return format_error(f"编辑文件超时", details=str(e), path=file_path)
    except Exception as e:
        logger.error(f"[写锁] {task_id} 异常: {file_path} - {e}")
        return format_error(f"编辑文件失败", details=str(e), path=file_path)


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
    task_id, manager, lock_enabled = get_task_context()
    
    # 无锁快速路径
    if not lock_enabled or manager is None:
        return _delete_file_impl(file_path)
    
    # 带锁路径
    logger.debug(f"[写锁] {task_id} 准备删除: {file_path}")
    try:
        result = _run_with_lock(
            _delete_file_async_with_lock(file_path, task_id, manager)
        )
        logger.debug(f"[写锁] {task_id} 完成删除: {file_path}")
        return result
    except TimeoutError as e:
        logger.error(f"[写锁] {task_id} 超时: {file_path} - {e}")
        return format_error(f"删除文件超时", details=str(e), path=file_path)
    except Exception as e:
        logger.error(f"[写锁] {task_id} 异常: {file_path} - {e}")
        return format_error(f"删除文件失败", details=str(e), path=file_path)


def list_directory(directory_path: str = ".", recursive: bool = False) -> list:
    """
    列出目录内容（只读操作，无需锁）
    
    Args:
        directory_path: 目录路径
        recursive: 是否递归列出
        
    Returns:
        目录内容列表
    """
    # list_directory 是只读操作，不需要锁
    return _list_directory_impl(directory_path, recursive)


# write_file_tool 是 write_file 的别名（为了兼容）
write_file_tool = write_file
