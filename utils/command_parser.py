"""
命令解析器 - 分析终端命令会访问哪些文件
"""

import re
import logging
from typing import List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class CommandFileAnalyzer:
    """
    分析命令会访问哪些文件，以及访问类型
    """
    
    # 命令模式定义：(正则表达式, (访问类型, 操作类型))
    COMMAND_PATTERNS = [
        # 删除命令（写锁）
        (r'^rm\s+(?:-[rfv]+\s+)?(.+)$', ('write', 'delete')),
        (r'^rmdir\s+(.+)$', ('write', 'delete')),
        (r'^del\s+(.+)$', ('write', 'delete')),  # Windows
        
        # 移动/重命名（写锁）
        (r'^mv\s+(?:-[fiv]+\s+)?(\S+)\s+(\S+)$', ('write', 'move')),
        (r'^move\s+(\S+)\s+(\S+)$', ('write', 'move')),  # Windows
        (r'^rename\s+(\S+)\s+(\S+)$', ('write', 'move')),
        
        # 复制（源读锁，目标写锁）
        (r'^cp\s+(?:-[rfv]+\s+)?(\S+)\s+(\S+)$', ('read_write', 'copy')),
        (r'^copy\s+(\S+)\s+(\S+)$', ('read_write', 'copy')),  # Windows
        
        # 就地修改（写锁）
        (r'^sed\s+-i\S*\s+.*\s+(\S+)$', ('write', 'edit')),
        (r'^awk\s+-i\S*\s+.*\s+(\S+)$', ('write', 'edit')),
        (r'^perl\s+-i\S*\s+.*\s+(\S+)$', ('write', 'edit')),
        
        # 输出重定向（写锁）
        (r'.+>\s*(\S+)$', ('write', 'redirect')),
        (r'.+>>\s*(\S+)$', ('write', 'append')),
        
        # Git 操作（写锁）
        (r'^git\s+add\s+(.+)$', ('write', 'git_add')),
        (r'^git\s+rm\s+(.+)$', ('write', 'git_rm')),
        (r'^git\s+mv\s+(\S+)\s+(\S+)$', ('write', 'git_mv')),
        
        # 只读命令（读锁）
        (r'^cat\s+(.+)$', ('read', 'read')),
        (r'^more\s+(.+)$', ('read', 'read')),
        (r'^less\s+(.+)$', ('read', 'read')),
        (r'^head\s+(?:-n\s*\d+\s+)?(.+)$', ('read', 'read')),
        (r'^tail\s+(?:-n\s*\d+\s+)?(.+)$', ('read', 'read')),
        (r'^grep\s+.+?\s+(.+)$', ('read', 'search')),
        (r'^find\s+.*-exec\s+cat\s+\{\}\s+', ('read', 'search')),
        
        # 归档/压缩（写锁）
        (r'^tar\s+.*[cf].*\s+(\S+)', ('write', 'archive')),
        (r'^zip\s+(\S+)', ('write', 'archive')),
        (r'^gzip\s+(.+)$', ('write', 'compress')),
        
        # 解压（写锁）
        (r'^tar\s+.*[xvf].*', ('write', 'extract')),
        (r'^unzip\s+(.+)$', ('write', 'extract')),
    ]
    
    @classmethod
    def analyze_command(cls, command: str) -> List[Tuple[str, str, str]]:
        """
        分析命令会访问的文件
        
        Args:
            command: 命令字符串
        
        Returns:
            List of (file_path, access_type, operation)
            - file_path: 文件路径
            - access_type: "read", "write", "read_write"
            - operation: "delete", "move", "copy", "edit", etc.
        """
        command = command.strip()
        
        if not command:
            return []
        
        # 检查是否包含管道或命令链（暂不支持详细解析）
        if any(op in command for op in ['|', '&&', '||', ';']):
            logger.warning(f"命令包含管道或命令链，无法完全解析: {command}")
            # 尝试解析第一个命令
            first_cmd = command.split('|')[0].split('&&')[0].split('||')[0].split(';')[0]
            command = first_cmd.strip()
        
        # 尝试匹配命令模式
        for pattern, (access_type, operation) in cls.COMMAND_PATTERNS:
            match = re.match(pattern, command)
            if match:
                return cls._extract_files(match, access_type, operation)
        
        # 无法识别的命令
        logger.debug(f"无法解析命令的文件访问: {command}")
        return []
    
    @classmethod
    def _extract_files(
        cls, 
        match: re.Match, 
        access_type: str, 
        operation: str
    ) -> List[Tuple[str, str, str]]:
        """从正则匹配中提取文件列表"""
        results = []
        groups = match.groups()
        
        if operation == 'move' or operation == 'git_mv':
            # 移动：源和目标都需要写锁
            if len(groups) >= 2:
                src, dst = groups[0], groups[1]
                results.append((src, 'write', f'{operation}_src'))
                results.append((dst, 'write', f'{operation}_dst'))
        
        elif operation == 'copy':
            # 复制：源读锁，目标写锁
            if len(groups) >= 2:
                src, dst = groups[0], groups[1]
                results.append((src, 'read', 'copy_src'))
                results.append((dst, 'write', 'copy_dst'))
        
        else:
            # 单一或多个文件操作
            for group in groups:
                if group:
                    # 分割多个文件参数
                    files = cls._parse_file_args(group)
                    for file_path in files:
                        # 过滤掉选项参数
                        if not file_path.startswith('-') and file_path:
                            results.append((file_path, access_type, operation))
        
        return results
    
    @classmethod
    def _parse_file_args(cls, arg_string: str) -> List[str]:
        """
        解析文件参数（处理空格分隔和引号）
        
        例如: "file1.txt file2.txt" 或 "'file with space.txt' file2.txt"
        """
        files = []
        
        # 简单分割（TODO: 更复杂的引号处理）
        parts = arg_string.split()
        
        current = ""
        in_quote = False
        
        for part in parts:
            if part.startswith('"') or part.startswith("'"):
                in_quote = True
                current = part[1:]
            elif (part.endswith('"') or part.endswith("'")) and in_quote:
                current += " " + part[:-1]
                files.append(current)
                current = ""
                in_quote = False
            elif in_quote:
                current += " " + part
            else:
                if part and not part.startswith('-'):
                    files.append(part)
        
        if current:
            files.append(current)
        
        return files
    
    @classmethod
    def is_dangerous_command(cls, command: str) -> bool:
        """
        判断命令是否危险（会修改文件系统）
        """
        dangerous_patterns = [
            r'^rm\s+',
            r'^rmdir\s+',
            r'^mv\s+',
            r'^sed\s+-i',
            r'.+>\s*\S+',  # 重定向
            r'^git\s+rm\s+',
        ]
        
        command = command.strip()
        return any(re.match(pat, command) for pat in dangerous_patterns)
    
    @classmethod
    def get_command_risk_level(cls, command: str) -> str:
        """
        评估命令的风险等级
        
        Returns:
            "low", "medium", "high"
        """
        command = command.strip()
        
        # 高风险：删除、覆盖
        if re.match(r'^(rm|rmdir|del)\s+', command):
            return "high"
        if re.match(r'.+>\s*\S+$', command):  # 重定向覆盖
            return "high"
        
        # 中等风险：移动、就地修改
        if re.match(r'^(mv|move|rename)\s+', command):
            return "medium"
        if re.match(r'^sed\s+-i', command):
            return "medium"
        
        # 低风险：只读操作
        if re.match(r'^(cat|grep|head|tail|less|more)\s+', command):
            return "low"
        
        # 默认中等风险
        return "medium"

