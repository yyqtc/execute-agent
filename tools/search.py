from pathlib import Path
from typing import List, Optional, Union
import os
import glob
import re
import threading
import multiprocessing
import logging

logger = logging.getLogger(__name__)
from concurrent.futures import ThreadPoolExecutor, as_completed

from .gitignore import get_project_root, load_gitignore_patterns, is_path_ignored


try:
    from utils.semantic_grep import semantic_grep

    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False


def search_files(pattern: str, root_dir: str = ".") -> list:
    """
    在指定根目录下根据 glob 模式搜索文件。

    Args:
        pattern: glob 模式字符串，用于匹配文件（例如: "*.py", "**/*.txt"）
        root_dir: 搜索的根目录路径，默认为当前目录（"."）

    Returns:
        匹配的文件路径列表。每个元素为匹配文件的绝对路径字符串。
        如果没有找到匹配的文件，返回空列表。
        如果发生错误，返回包含错误信息的列表。

    功能说明:
        - 使用 glob 标准库进行模式匹配
        - 支持标准的 glob 模式语法（如 *, ?, [字符集]）
        - 支持递归搜索（使用 ** 模式，如 "**/*.py"）
        - 返回的路径为绝对路径
        - 只返回文件，不包括目录
    """
    try:
        # 获取项目根目录
        project_root = get_project_root()

        # 加载 .gitignore 模式
        ignore_patterns, negation_patterns = load_gitignore_patterns(str(project_root))

        # 解析根目录路径
        root_path = os.path.abspath(root_dir)

        # 检查根目录是否存在
        if not os.path.exists(root_path):
            return [f"错误: 根目录不存在。路径: {root_dir}"]

        # 检查是否为目录
        if not os.path.isdir(root_path):
            return [f"错误: 根路径不是目录。路径: {root_dir}"]

        # 检查读取权限
        if not os.access(root_path, os.R_OK):
            return [f"错误: 没有读取权限。路径: {root_dir}"]

        # 构建搜索模式（将相对模式转换为绝对路径模式）
        if os.path.isabs(pattern):
            # 如果模式已经是绝对路径，直接使用
            search_pattern = pattern
        else:
            # 如果模式是相对路径，将其与根目录组合
            search_pattern = os.path.join(root_path, pattern)

        # 使用 glob 进行搜索
        # glob.glob 返回匹配的路径列表
        matched_files = glob.glob(search_pattern, recursive=True)

        # 过滤出只包含文件的路径（排除目录），并应用 .gitignore 规则
        # 使用 ThreadPoolExecutor 并行处理文件过滤
        result = []
        project_root_str = str(project_root)
        results_lock = threading.Lock()

        def filter_file(path: str) -> Optional[str]:
            """过滤单个文件，检查是否为文件且不被 .gitignore 忽略"""
            if not os.path.isfile(path):
                return None

            # 计算相对于项目根目录的路径
            try:
                rel_path = os.path.relpath(os.path.abspath(path), project_root_str)
            except ValueError:
                # 如果路径不在项目根目录下，跳过
                return None

            # 检查是否被 .gitignore 忽略
            if not is_path_ignored(rel_path, ignore_patterns, negation_patterns):
                return os.path.abspath(path)
            return None

        # 计算线程池大小：根据文件数量和CPU核心数动态调整
        max_workers = min(len(matched_files), multiprocessing.cpu_count() * 2, 32)
        max_workers = max(1, max_workers)

        # 使用线程池并行过滤文件
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(filter_file, path): path for path in matched_files
            }

            for future in as_completed(future_to_path):
                try:
                    filtered_path = future.result()
                    if filtered_path:
                        with results_lock:
                            result.append(filtered_path)
                except Exception as e:
                    logging.error(
                        f"过滤文件失败，文件路径: {future_to_path[future]}, 错误: {str(e)}"
                    )

        return result

    except PermissionError as e:
        return [
            f"错误: 权限不足，无法搜索文件。根目录: {root_dir}, 模式: {pattern}, 错误: {str(e)}"
        ]
    except Exception as e:
        return [
            f"错误: 搜索文件时发生未知错误。根目录: {root_dir}, 模式: {pattern}, 错误: {str(e)}"
        ]


def grep(
    pattern: str,
    path: str = ".",
    file_type: Optional[str] = None,
    case_sensitive: bool = False,
    context_lines: int = 0,
    output_mode: str = "content",
    semantic_search: bool = True,
    similarity_threshold: float = 0.3,
) -> Union[str, List[str], dict]:
    """
    使用正则表达式或语义搜索在文件中搜索模式，支持多文件、递归搜索、上下文显示和文件类型过滤。

    Args:
        pattern: 搜索模式字符串（正则表达式或自然语言查询）
        path: 搜索路径，可以是文件或目录，默认为当前目录（"."）
        file_type: 文件类型过滤（可选），例如 "*.py", "*.txt" 等，支持 glob 模式
        case_sensitive: 是否区分大小写，默认为 False（仅对正则搜索有效）
        context_lines: 上下文行数，默认为 0（不显示上下文）
        output_mode: 输出模式，可选值：
            - "content": 返回匹配行（带上下文），格式为字符串
            - "files": 返回匹配的文件列表，格式为列表
            - "count": 返回统计信息，格式为字典
        semantic_search: 是否使用语义搜索，默认为 True
        similarity_threshold: 语义搜索的相似度阈值，默认为 0.3（仅对语义搜索有效）

    Returns:
        根据 output_mode 返回不同格式的结果：
        - "content": 字符串，包含所有匹配行及其上下文
        - "files": 列表，包含所有匹配的文件路径
        - "count": 字典，包含统计信息（总匹配数、文件数等）

    功能说明:
        - 当 semantic_search=True 时，使用语义搜索（需要安装 sentence-transformers 和 faiss-cpu）
        - 当 semantic_search=False 时，使用传统的正则表达式搜索
        - 支持单文件或目录（递归）搜索
        - 支持文件类型过滤（使用 glob 模式）
        - 支持上下文显示（匹配行前后 N 行）
        - 自动跳过二进制文件和无法读取的文件
        - 并行搜索优化：使用 ThreadPoolExecutor 并行处理多个文件的搜索任务，大幅提升搜索性能
        - 线程池大小配置：根据文件数量和 CPU 核心数动态调整，计算公式为 min(文件数, CPU核心数 * 2, 32)，确保至少为 1 个线程
        - 性能优化：通过并行搜索可以显著减少多文件搜索的总体耗时，特别是在处理大量文件时效果明显
    """
    # 如果启用语义搜索且模块可用，使用语义搜索
    if semantic_search and SEMANTIC_SEARCH_AVAILABLE:
        try:
            return semantic_grep(
                query=pattern,
                path=path,
                file_type=file_type,
                context_lines=context_lines,
                output_mode=output_mode,
                similarity_threshold=similarity_threshold,
            )
        except Exception as e:
            # 如果语义搜索失败，回退到正则搜索
            logging.error(f"语义搜索失败，路径: {path}, 错误: {str(e)}")

    # 使用传统的正则表达式搜索
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
                logging.error(f"搜索文件失败，文件路径: {file_path}, 错误: {str(e)}")

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
                except Exception as e:
                    logging.error(
                        f"处理搜索结果失败，文件路径: {file_path}, 错误: {str(e)}"
                    )

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


def _extract_keywords(query: str) -> List[str]:
    """
    从自然语言查询中提取关键词

    Args:
        query: 自然语言查询字符串

    Returns:
        关键词列表
    """
    # 简单的停用词列表（可以根据需要扩展）
    stop_words = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "can",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "with",
        "by",
        "from",
        "as",
        "and",
        "or",
        "but",
        "if",
        "then",
        "that",
        "this",
        "these",
        "those",
        "what",
        "which",
        "who",
        "where",
        "when",
        "why",
        "how",
        "how",
        "all",
        "each",
        "every",
        "some",
        "any",
        "no",
        "not",
        "only",
        "just",
        "also",
        "more",
        "most",
        "very",
        "too",
        "so",
        "such",
        "than",
        "then",
        "there",
        "here",
        "where",
        "when",
        "查找",
        "搜索",
        "找",
        "的",
        "了",
        "在",
        "是",
        "有",
        "和",
        "与",
        "或",
        "但",
        "如果",
        "那么",
        "这个",
        "那个",
        "这些",
        "那些",
        "什么",
        "哪个",
        "谁",
        "哪里",
        "何时",
        "为什么",
        "如何",
        "所有",
        "每个",
        "一些",
        "任何",
        "没有",
        "不",
        "只",
        "也",
        "更",
        "最",
        "非常",
        "太",
        "所以",
        "这样",
        "那样",
        "那里",
        "这里",
    }

    # 将查询转换为小写并分割成单词
    # 使用正则表达式提取单词（包括中文字符）
    words = re.findall(r"\b\w+\b|[a-zA-Z]+|[\u4e00-\u9fff]+", query.lower())

    # 过滤停用词和短词（长度小于2的词）
    keywords = [word for word in words if word not in stop_words and len(word) >= 2]

    # 如果没有提取到关键词，返回原始查询（去除停用词后）
    if not keywords:
        # 如果所有词都是停用词，至少返回一些有意义的词
        meaningful_words = [word for word in words if len(word) >= 2]
        if meaningful_words:
            return meaningful_words
        # 如果还是没有，返回原始查询的单词
        return [word for word in words if word]

    return keywords


def _search_in_file(
    file_path: str, keywords: List[str], max_results: int = 50
) -> List[dict]:
    """
    在文件中搜索关键词，返回匹配的行

    Args:
        file_path: 文件路径
        keywords: 关键词列表
        max_results: 最大返回结果数

    Returns:
        匹配结果列表，每个元素包含 file_path, line_number, content
    """
    results = []

    try:
        # 检查文件是否存在
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return results

        # 检查读取权限
        if not os.access(file_path, os.R_OK):
            return results

        # 读取文件内容
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, IOError):
            # 如果无法读取（可能是二进制文件），跳过
            return results

        # 在每一行中搜索关键词
        for line_num, line in enumerate(lines, start=1):
            line_lower = line.lower()
            # 检查是否包含任何关键词
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in line_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                results.append(
                    {
                        "file_path": os.path.abspath(file_path),
                        "line_number": line_num,
                        "content": line.rstrip("\n\r"),
                        "matched_keywords": matched_keywords,
                    }
                )

                # 限制结果数量
                if len(results) >= max_results:
                    break

    except Exception as e:
        # 忽略错误，继续搜索其他文件
        logging.error(f"搜索文件失败，文件路径: {file_path}, 错误: {str(e)}")

    return results


def codebase_search(
    query: str,
    target_directories: Optional[List[str]] = None,
    file_pattern: Optional[str] = None,
) -> str:
    """
    基于关键词搜索代码库，返回匹配的代码片段列表

    Args:
        query: 搜索查询（自然语言或关键词）
        target_directories: 目标目录列表（可选），如果未提供则搜索当前目录
        file_pattern: 文件类型过滤模式（可选），例如 "*.py", "*.js" 等

    Returns:
        JSON 格式字符串，包含匹配的代码片段列表。每个元素包含：
        - file_path: 文件路径
        - line_number: 行号
        - content: 代码内容
        - matched_keywords: 匹配的关键词列表

    功能说明:
        - 从自然语言查询中提取关键词
        - 支持目录范围限制（target_directories）
        - 支持文件类型过滤（file_pattern）
        - 返回匹配的代码片段，包含文件路径、行号和代码内容
        - 并行搜索优化：使用 ThreadPoolExecutor 并行收集文件和搜索文件内容，大幅提升搜索性能
        - 线程池大小配置：根据目录数量或文件数量以及 CPU 核心数动态调整，计算公式为 min(目录数/文件数, CPU核心数 * 2, 32)，确保至少为 1 个线程
        - 性能优化：通过并行处理文件收集和文件搜索两个阶段，可以显著减少大规模代码库搜索的总体耗时，特别是在处理多个目录和大量文件时效果明显
    """
    import json

    try:
        # 从查询中提取关键词
        keywords = _extract_keywords(query)

        if not keywords:
            return json.dumps(
                {"error": "无法从查询中提取关键词", "query": query},
                ensure_ascii=False,
                indent=2,
            )

        # 确定搜索目录
        if target_directories:
            search_dirs = [os.path.abspath(d) for d in target_directories]
        else:
            # 默认搜索当前目录
            search_dirs = [os.path.abspath(".")]

        # 验证目录是否存在
        valid_dirs = []
        for dir_path in search_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                if os.access(dir_path, os.R_OK):
                    valid_dirs.append(dir_path)

        if not valid_dirs:
            return json.dumps(
                {
                    "error": "没有有效的搜索目录",
                    "target_directories": target_directories,
                },
                ensure_ascii=False,
                indent=2,
            )

        # 获取项目根目录（向上查找包含 .gitignore 的目录）
        project_root_path = get_project_root()
        project_root = str(project_root_path)
        
        # 从项目根目录统一读取 .gitignore
        ignore_patterns, negation_patterns = load_gitignore_patterns(project_root)

        # 收集要搜索的文件（并行化）
        files_to_search = []
        files_lock = threading.Lock()

        def collect_files_from_dir(
            dir_path: str,
            ignore_patterns: List[str],
            negation_patterns: List[str],
            project_root: str,
        ) -> List[str]:
            """从单个目录收集文件"""
            local_files = []

            if file_pattern:
                # 使用文件模式过滤
                pattern = file_pattern
                if not os.path.isabs(pattern):
                    # 构建搜索模式
                    search_pattern = os.path.join(dir_path, "**", pattern)
                else:
                    search_pattern = pattern

                matched_files = glob.glob(search_pattern, recursive=True)
                for file_path in matched_files:
                    if os.path.isfile(file_path):
                        # 检查是否被 .gitignore 忽略（使用相对于项目根目录的路径）
                        rel_path = os.path.relpath(file_path, project_root)
                        if not is_path_ignored(
                            rel_path, ignore_patterns, negation_patterns
                        ):
                            local_files.append(file_path)
            else:
                # 搜索所有文件（递归）
                for root, dirs, files in os.walk(dir_path):
                    # 创建相对于项目根目录的路径用于匹配
                    rel_root = os.path.relpath(root, project_root)
                    if rel_root == ".":
                        rel_root = ""

                    # 过滤需要跳过的目录（使用 .gitignore）
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
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            # 检查文件是否被 .gitignore 忽略（使用相对于项目根目录的路径）
                            file_rel_path = (
                                os.path.join(rel_root, file) if rel_root else file
                            )
                            if not is_path_ignored(
                                file_rel_path, ignore_patterns, negation_patterns
                            ):
                                local_files.append(file_path)

            return local_files

        # 使用线程池并行收集文件
        max_workers = min(len(valid_dirs), multiprocessing.cpu_count() * 2, 32)
        max_workers = max(1, max_workers)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dir = {
                executor.submit(
                    collect_files_from_dir,
                    dir_path,
                    ignore_patterns,
                    negation_patterns,
                    project_root,
                ): dir_path
                for dir_path in valid_dirs
            }

            for future in as_completed(future_to_dir):
                dir_path = future_to_dir[future]
                try:
                    dir_files = future.result()
                    with files_lock:
                        files_to_search.extend(dir_files)
                except Exception as e:
                    logging.error(f"收集文件失败，目录路径: {dir_path}, 错误: {str(e)}")

        # 去重
        files_to_search = list(set(files_to_search))

        # 并行搜索所有文件
        all_results = []
        results_lock = threading.Lock()

        def search_file_safe(file_path: str) -> List[dict]:
            """线程安全的文件搜索包装函数"""
            try:
                return _search_in_file(file_path, keywords)
            except Exception:
                return []

        # 计算线程池大小：根据文件数量和CPU核心数动态调整
        max_workers = min(len(files_to_search), multiprocessing.cpu_count() * 2, 32)
        max_workers = max(1, max_workers)

        # 使用线程池并行搜索
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(search_file_safe, file_path): file_path
                for file_path in files_to_search
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_results = future.result()
                    with results_lock:
                        all_results.extend(file_results)
                except Exception as e:
                    logging.error(
                        f"搜索文件失败，文件路径: {file_path}, 错误: {str(e)}"
                    )

        # 按文件路径和行号排序
        all_results.sort(key=lambda x: (x["file_path"], x["line_number"]))

        # 构建返回结果
        result = {
            "query": query,
            "keywords": keywords,
            "search_directories": valid_dirs,
            "file_pattern": file_pattern,
            "total_files_searched": len(files_to_search),
            "total_matches": len(all_results),
            "matches": all_results[:100],  # 限制返回最多100个结果
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"搜索代码库时发生错误: {str(e)}", "query": query},
            ensure_ascii=False,
            indent=2,
        )
