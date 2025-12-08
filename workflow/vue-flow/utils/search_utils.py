from tools.search import codebase_search as codebase_search_impl
from typing import Optional, List

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
    return codebase_search_impl(query, target_directories, file_pattern)
