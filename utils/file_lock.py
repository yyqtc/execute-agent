"""
文件访问管理器 - 支持读写锁机制，防止并行任务中的文件冲突
"""

import asyncio
import logging
from typing import Dict, Set, Optional
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class FileAccessManager:
    """
    文件访问管理器，实现读写锁机制
    
    特性：
    - 支持多个读者同时访问（共享锁）
    - 写入时独占访问（排他锁）
    - 防止死锁（按文件路径排序申请锁）
    - 支持超时控制
    """
    
    def __init__(self):
        # 存储每个文件的读者集合 {file_path: set(task_ids)}
        self._readers: Dict[str, Set[str]] = {}
        
        # 存储每个文件的写者 {file_path: task_id}
        self._writers: Dict[str, str] = {}
        
        # 全局锁，用于保护上述数据结构
        self._global_lock = asyncio.Lock()
        
        # 统计信息
        self._stats = {
            "read_locks_acquired": 0,
            "write_locks_acquired": 0,
            "lock_timeouts": 0,
            "lock_contentions": 0
        }
    
    def _normalize_path(self, file_path: str) -> str:
        """标准化文件路径"""
        try:
            return str(Path(file_path).resolve())
        except Exception:
            return file_path
    
    @asynccontextmanager
    async def read_lock(
        self, 
        file_path: str, 
        task_id: str,
        timeout: Optional[float] = 5.0
    ):
        """
        获取读锁（共享锁）
        
        多个任务可以同时持有读锁，但读锁期间不能获取写锁
        
        Args:
            file_path: 文件路径
            task_id: 任务ID（用于追踪和调试）
            timeout: 超时时间（秒），None表示无限等待
        
        Raises:
            TimeoutError: 等待锁超时
        """
        normalized_path = self._normalize_path(file_path)
        wait_start = asyncio.get_event_loop().time()
        lock_acquired = False
        
        try:
            # 等待直到可以获取读锁
            while True:
                async with self._global_lock:
                    # 检查是否有写者
                    has_writer = normalized_path in self._writers
                    
                    if not has_writer:
                        # 可以获取读锁
                        if normalized_path not in self._readers:
                            self._readers[normalized_path] = set()
                        self._readers[normalized_path].add(task_id)
                        self._stats["read_locks_acquired"] += 1
                        lock_acquired = True
                        logger.debug(
                            f"[读锁] {task_id} 获取 {file_path} 的读锁 "
                            f"(当前读者: {len(self._readers[normalized_path])})"
                        )
                        break
                    else:
                        # 记录冲突
                        self._stats["lock_contentions"] += 1
                
                # 检查超时
                if timeout is not None:
                    elapsed = asyncio.get_event_loop().time() - wait_start
                    if elapsed >= timeout:
                        self._stats["lock_timeouts"] += 1
                        raise TimeoutError(
                            f"任务 {task_id} 等待 {file_path} 读锁超时 "
                            f"({timeout:.1f}秒), 当前被 {self._writers.get(normalized_path)} 写入"
                        )
                
                # 短暂等待后重试
                await asyncio.sleep(0.05)
            
            # 释放控制权，让调用者执行操作
            yield
            
        finally:
            # 释放读锁
            if lock_acquired:
                async with self._global_lock:
                    if normalized_path in self._readers:
                        self._readers[normalized_path].discard(task_id)
                        remaining = len(self._readers[normalized_path])
                        if remaining == 0:
                            del self._readers[normalized_path]
                        logger.debug(
                            f"[读锁] {task_id} 释放 {file_path} 的读锁 "
                            f"(剩余读者: {remaining})"
                        )
    
    @asynccontextmanager
    async def write_lock(
        self, 
        file_path: str, 
        task_id: str,
        timeout: Optional[float] = 10.0
    ):
        """
        获取写锁（排他锁）
        
        只有一个任务可以持有写锁，写锁期间不能有任何读锁或写锁
        
        Args:
            file_path: 文件路径
            task_id: 任务ID
            timeout: 超时时间（秒），None表示无限等待
        
        Raises:
            TimeoutError: 等待锁超时
        """
        normalized_path = self._normalize_path(file_path)
        wait_start = asyncio.get_event_loop().time()
        lock_acquired = False
        
        try:
            # 等待直到可以获取写锁
            while True:
                async with self._global_lock:
                    # 检查是否有读者或写者
                    has_readers = normalized_path in self._readers and self._readers[normalized_path]
                    has_writer = normalized_path in self._writers
                    
                    if not has_readers and not has_writer:
                        # 可以获取写锁
                        self._writers[normalized_path] = task_id
                        self._stats["write_locks_acquired"] += 1
                        lock_acquired = True
                        logger.debug(f"[写锁] {task_id} 获取 {file_path} 的写锁")
                        break
                    else:
                        # 记录冲突
                        self._stats["lock_contentions"] += 1
                
                # 检查超时
                if timeout is not None:
                    elapsed = asyncio.get_event_loop().time() - wait_start
                    if elapsed >= timeout:
                        self._stats["lock_timeouts"] += 1
                        conflict_info = []
                        if has_readers:
                            conflict_info.append(f"读者: {self._readers[normalized_path]}")
                        if has_writer:
                            conflict_info.append(f"写者: {self._writers[normalized_path]}")
                        raise TimeoutError(
                            f"任务 {task_id} 等待 {file_path} 写锁超时 "
                            f"({timeout:.1f}秒), 冲突: {', '.join(conflict_info)}"
                        )
                
                # 短暂等待后重试
                await asyncio.sleep(0.05)
            
            # 释放控制权，让调用者执行操作
            yield
            
        finally:
            # 释放写锁
            if lock_acquired:
                async with self._global_lock:
                    if self._writers.get(normalized_path) == task_id:
                        del self._writers[normalized_path]
                        logger.debug(f"[写锁] {task_id} 释放 {file_path} 的写锁")
    
    async def try_read_lock(
        self, 
        file_path: str, 
        task_id: str
    ) -> bool:
        """
        尝试立即获取读锁（非阻塞）
        
        Returns:
            True: 成功获取锁
            False: 无法获取锁（有写者）
        """
        normalized_path = self._normalize_path(file_path)
        
        async with self._global_lock:
            has_writer = normalized_path in self._writers
            
            if not has_writer:
                if normalized_path not in self._readers:
                    self._readers[normalized_path] = set()
                self._readers[normalized_path].add(task_id)
                return True
            
            return False
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self._stats,
            "active_readers": sum(len(readers) for readers in self._readers.values()),
            "active_writers": len(self._writers),
            "locked_files": len(self._readers) + len(self._writers)
        }
    
    def get_lock_status(self, file_path: str) -> dict:
        """
        获取指定文件的锁状态
        
        Returns:
            {
                "has_readers": bool,
                "reader_count": int,
                "readers": list,
                "has_writer": bool,
                "writer": str or None
            }
        """
        normalized_path = self._normalize_path(file_path)
        
        return {
            "has_readers": normalized_path in self._readers,
            "reader_count": len(self._readers.get(normalized_path, set())),
            "readers": list(self._readers.get(normalized_path, set())),
            "has_writer": normalized_path in self._writers,
            "writer": self._writers.get(normalized_path)
        }


# 全局文件访问管理器实例
_global_file_manager: Optional[FileAccessManager] = None


def get_file_manager() -> FileAccessManager:
    """获取全局文件访问管理器"""
    global _global_file_manager
    if _global_file_manager is None:
        _global_file_manager = FileAccessManager()
    return _global_file_manager


def reset_file_manager():
    """重置文件访问管理器（主要用于测试）"""
    global _global_file_manager
    _global_file_manager = None

