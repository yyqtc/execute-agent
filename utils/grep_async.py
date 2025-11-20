"""
异步grep搜索工具
使用ThreadPoolExecutor实现多个文件的异步搜索，支持.gitignore排除规则
"""

from pathlib import Path
from typing import List, Optional, Union
import os
import glob
import re
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

from tools.gitignore import get_project_root, load_gitignore_patterns, is_path_ignored


def grep(
    pattern: str,
    path: str = ".",
    file_type: Optional[str] = None,
    case_sensitive: bool = False,
    context_lines: int = 0,
    output_mode: str = "content",
) -> Union[str, List[str], dict]:
    """
    使用正则表达式在文件中搜索模式，支持多文件、递归搜索、上下文显示和文件类型过滤。
    使用ThreadPoolExecutor实现多个文件的异步搜索。

    Args:
        pattern: 搜索模式字符串（正则表达式）
        path: 搜索路径，可以是文件或目录，默认为当前目录（"."）
        file_type: 文件类型过滤（可选），例如 "*.py", "*.txt" 等，支持 glob 模式
        case_sensitive: 是否区分大小写，默认为 False
        context_lines: 上下文行数，默认为 0（不显示上下文）
        output_mode: 输出模式，可选值：
            - "content": 返回匹配行（带上下文），格式为字符串
            - "files": 返回匹配的文件列表，格式为列表
            - "count": 返回统计信息，格式为字典

    Returns:
        根据 output_mode 返回不同格式的结果：
        - "content": 字符串，包含所有匹配行及其上下文
        - "files": 列表，包含所有匹配的文件路径
        - "count": 字典，包含统计信息（总匹配数、文件数等）

    功能说明:
        - 使用传统的正则表达式搜索
        - 支持单文件或目录（递归）搜索
        - 支持文件类型过滤（使用 glob 模式）
        - 支持上下文显示（匹配行前后 N 行）
        - 自动跳过二进制文件和无法读取的文件
        - 读取.gitignore并排除其中的文件和目录
        - 使用ThreadPoolExecutor并行搜索多个文件，提升搜索性能
        - 线程池大小根据文件数量和CPU核心数动态调整
    """
    try:
        # 编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            error_msg = f"错误: 无效的正则表达式模式 '{pattern}': {str(e)}"
            if output_mode == "content":
                return error_msg
            elif output_mode == "files":
                return []
            else:  # count
                return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}

        # 解析搜索路径
        search_path = Path(path).resolve()

        # 检查路径是否存在
        if not search_path.exists():
            error_msg = f"错误: 路径不存在。路径: {path}"
            if output_mode == "content":
                return error_msg
            elif output_mode == "files":
                return []
            else:  # count
                return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}

        # 获取项目根目录和 .gitignore 模式
        project_root = get_project_root()
        ignore_patterns, negation_patterns = load_gitignore_patterns(str(project_root))

        # 收集要搜索的文件列表
        files_to_search = []

        if search_path.is_file():
            # 如果是文件，检查是否被 .gitignore 忽略
            rel_file_path = os.path.relpath(str(search_path), str(project_root))
            if not is_path_ignored(rel_file_path, ignore_patterns, negation_patterns):
                files_to_search.append(search_path)
        elif search_path.is_dir():
            # 如果是目录，递归收集文件
            if file_type:
                # 使用文件类型过滤
                if os.path.isabs(file_type):
                    search_pattern = file_type
                else:
                    # 构建递归搜索模式
                    search_pattern = str(search_path / "**" / file_type)
                matched_files = glob.glob(search_pattern, recursive=True)
                for file_path in matched_files:
                    file_path_obj = Path(file_path)
                    if file_path_obj.is_file():
                        # 检查是否被 .gitignore 忽略
                        rel_file_path = os.path.relpath(
                            str(file_path_obj), str(project_root)
                        )
                        if not is_path_ignored(
                            rel_file_path, ignore_patterns, negation_patterns
                        ):
                            files_to_search.append(file_path_obj)
            else:
                # 搜索所有文件
                for root, dirs, files in os.walk(search_path):
                    # 创建相对于项目根目录的路径用于匹配
                    rel_root = os.path.relpath(root, str(project_root))
                    if rel_root == ".":
                        rel_root = ""
                    # 使用 .gitignore 规则过滤目录
                    dirs[:] = [
                        d
                        for d in dirs
                        if not is_path_ignored(
                            os.path.join(rel_root, d) if rel_root else d,
                            ignore_patterns,
                            negation_patterns,
                        )
                    ]
                    for file in files:
                        file_path = Path(root) / file
                        if file_path.is_file():
                            # 检查是否被 .gitignore 忽略
                            file_rel_path = (
                                os.path.join(rel_root, file) if rel_root else file
                            )
                            if not is_path_ignored(
                                file_rel_path, ignore_patterns, negation_patterns
                            ):
                                files_to_search.append(file_path)
        else:
            error_msg = f"错误: 路径既不是文件也不是目录。路径: {path}"
            if output_mode == "content":
                return error_msg
            elif output_mode == "files":
                return []
            else:  # count
                return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}

        # 如果没有文件需要搜索，返回空结果
        if not files_to_search:
            if output_mode == "content":
                return f"未找到匹配 '{pattern}' 的内容"
            elif output_mode == "files":
                return []
            else:  # count
                return {
                    "pattern": pattern,
                    "path": path,
                    "file_type": file_type,
                    "case_sensitive": case_sensitive,
                    "total_matches": 0,
                    "files_with_matches": 0,
                    "files_searched": 0,
                }

        # 存储匹配结果
        matches = []
        matched_files_set = set()
        total_matches = 0
        results_lock = threading.Lock()

        def search_file_regex(file_path: Path) -> List[dict]:
            """在单个文件中搜索正则模式"""
            file_matches = []
            try:
                # 检查读取权限
                if not os.access(file_path, os.R_OK):
                    return file_matches

                # 尝试读取文件（使用 UTF-8 编码）
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except (UnicodeDecodeError, IOError):
                    # 如果无法读取（可能是二进制文件），跳过
                    return file_matches

                # 在每一行中搜索模式
                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        # 获取上下文
                        context_before = []
                        context_after = []

                        if context_lines > 0:
                            # 获取前面的上下文
                            start_idx = max(0, line_num - context_lines - 1)
                            for i in range(start_idx, line_num - 1):
                                if i < len(lines):
                                    context_before.append(
                                        (i + 1, lines[i].rstrip("\n\r"))
                                    )

                            # 获取后面的上下文
                            end_idx = min(len(lines), line_num + context_lines)
                            for i in range(line_num, end_idx):
                                if i < len(lines):
                                    context_after.append(
                                        (i + 1, lines[i].rstrip("\n\r"))
                                    )

                        file_matches.append(
                            {
                                "file_path": str(file_path),
                                "line_number": line_num,
                                "content": line.rstrip("\n\r"),
                                "context_before": context_before,
                                "context_after": context_after,
                            }
                        )

            except Exception as e:
                pass

            return file_matches

        # 计算线程池大小：根据文件数量和CPU核心数动态调整
        max_workers = min(len(files_to_search), multiprocessing.cpu_count() * 2, 32)
        max_workers = max(1, max_workers)

        # 使用线程池并行搜索
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(search_file_regex, file_path): file_path
                for file_path in files_to_search
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_matches = future.result()
                    with results_lock:
                        matches.extend(file_matches)
                        for match in file_matches:
                            matched_files_set.add(match["file_path"])
                            total_matches += 1
                except Exception:
                    pass

        # 根据 output_mode 返回结果
        if output_mode == "content":
            # 返回匹配行（带上下文）的字符串格式
            if not matches:
                return f"未找到匹配 '{pattern}' 的内容"

            result_lines = []
            current_file = None

            for match in matches:
                file_path = match["file_path"]
                line_num = match["line_number"]
                content = match["content"]
                context_before = match["context_before"]
                context_after = match["context_after"]

                # 如果是新文件，添加文件分隔符
                if file_path != current_file:
                    if current_file is not None:
                        result_lines.append("")
                    result_lines.append(f"文件: {file_path}")
                    current_file = file_path

                # 添加上下文（前面的行）
                for ctx_line_num, ctx_content in context_before:
                    result_lines.append(f"  {ctx_line_num:4d}: {ctx_content}")

                # 添加匹配行（标记）
                result_lines.append(f"  {line_num:4d}: {content}  <-- 匹配")

                # 添加上下文（后面的行）
                for ctx_line_num, ctx_content in context_after:
                    result_lines.append(f"  {ctx_line_num:4d}: {ctx_content}")

            return "\n".join(result_lines)

        elif output_mode == "files":
            # 返回匹配的文件列表
            return sorted(list(matched_files_set))

        else:  # output_mode == "count"
            # 返回统计信息
            return {
                "pattern": pattern,
                "path": path,
                "file_type": file_type,
                "case_sensitive": case_sensitive,
                "total_matches": total_matches,
                "files_with_matches": len(matched_files_set),
                "files_searched": len(files_to_search),
            }

    except PermissionError as e:
        error_msg = f"错误: 权限不足，无法访问路径。路径: {path}, 错误: {str(e)}"
        if output_mode == "content":
            return error_msg
        elif output_mode == "files":
            return []
        else:  # count
            return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}
    except Exception as e:
        error_msg = f"错误: grep 搜索时发生未知错误。路径: {path}, 错误: {str(e)}"
        if output_mode == "content":
            return error_msg
        elif output_mode == "files":
            return []
        else:  # count
            return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}
