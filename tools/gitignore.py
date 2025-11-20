import os
from pathlib import Path
import fnmatch
import logging

logger = logging.getLogger(__name__)


def load_gitignore_patterns(root_dir: str) -> tuple:
    """
    从根目录读取 .gitignore 模式列表

    Args:
        root_dir: 根目录路径

    Returns:
        (忽略模式列表, 否定模式列表) 的元组
    """
    gitignore_path = os.path.join(root_dir, ".gitignore")
    ignore_patterns = ["__pycache__/", ".git/", ".mypy_cache/", ".pytest_cache/", ".semantic_cache/"]
    negation_patterns = []

    if os.path.exists(gitignore_path) and os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    # 移除行尾的换行符和空白字符
                    line = line.rstrip("\n\r").strip()
                    # 跳过空行和注释行
                    if not line or line.startswith("#"):
                        continue
                    # 处理否定模式（以 ! 开头）
                    if line.startswith("!"):
                        negation_pattern = line[1:].strip()
                        if negation_pattern:
                            negation_patterns.append(negation_pattern)
                    else:
                        # 普通忽略模式
                        if line not in ignore_patterns:
                            ignore_patterns.append(line)

        except (IOError, OSError, UnicodeDecodeError) as e:
            # 如果读取文件失败，返回空列表
            logging.error(
                f"读取 .gitignore 文件失败，路径: {gitignore_path}, 错误: {str(e)}"
            )

    return (ignore_patterns, negation_patterns)


def _match_pattern(path: str, pattern: str) -> bool:
    """
    检查路径是否匹配 gitignore 模式

    Args:
        path: 要检查的相对路径（已统一使用 / 作为分隔符）
        pattern: gitignore 模式（已统一使用 / 作为分隔符）

    Returns:
        如果路径匹配模式返回 True，否则返回 False
    """
    # 空模式不匹配任何路径
    if not pattern:
        return False

    # 规范化路径和模式
    path = path.strip()
    pattern = pattern.strip()

    # 如果模式以 / 开头，只匹配根目录下的路径
    if pattern.startswith("/"):
        pattern = pattern[1:]
        # 检查是否完全匹配或路径以 / 继续
        if path == pattern:
            return True
        if path.startswith(pattern + "/"):
            return True
        return False

    # 如果模式以 / 结尾，只匹配目录（但当前实现不区分文件和目录）
    is_dir_pattern = pattern.endswith("/")
    if is_dir_pattern:
        pattern = pattern[:-1]

    # 检查完全匹配
    if path == pattern:
        return True

    # 检查路径前缀匹配（模式在路径开头）
    if path.startswith(pattern + "/"):
        return True

    # 检查路径后缀匹配（模式在路径末尾）
    if path.endswith("/" + pattern):
        return True

    # 检查路径中间匹配（模式在路径中间）
    if "/" + pattern + "/" in path:
        return True

    # 如果模式包含通配符，使用 fnmatch 进行匹配
    if "*" in pattern or "?" in pattern:
        # 检查完全匹配
        if fnmatch.fnmatch(path, pattern):
            return True
        # 检查路径前缀匹配
        if fnmatch.fnmatch(path, pattern + "/*"):
            return True
        # 检查路径后缀匹配
        if fnmatch.fnmatch(path, "*/" + pattern):
            return True
        # 检查路径中间匹配
        path_parts = path.split("/")
        pattern_parts = pattern.split("/")
        if len(pattern_parts) == 1:
            # 单部分模式，检查是否在任何位置匹配
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        else:
            # 多部分模式，检查路径是否包含匹配的部分
            for i in range(len(path_parts) - len(pattern_parts) + 1):
                if all(
                    fnmatch.fnmatch(path_parts[i + j], pattern_parts[j])
                    for j in range(len(pattern_parts))
                ):
                    return True

    return False


def is_path_ignored(
    path: str, ignore_patterns: list, negation_patterns: list = None
) -> bool:
    """
    检查路径是否被 .gitignore 规则忽略

    Args:
        path: 要检查的相对路径
        ignore_patterns: .gitignore 中的忽略模式列表
        negation_patterns: .gitignore 中的否定模式列表（可选）

    Returns:
        如果路径被忽略返回 True，否则返回 False
    """
    if negation_patterns is None:
        negation_patterns = []

    # 规范化路径
    if not path:
        return False

    # 将路径分隔符统一为 /
    path = path.replace("\\", "/")

    # 移除开头的 ./ 或 ./
    if path.startswith("./"):
        path = path[2:]

    # 处理 . 或空路径
    if path == "." or path == "":
        path = ""

    # 移除末尾的 /
    path = path.rstrip("/")

    # 先检查是否匹配忽略规则
    matched_ignore = False
    for pattern in ignore_patterns:
        if not pattern:
            continue
        pattern = pattern.strip().replace("\\", "/")
        if _match_pattern(path, pattern):
            matched_ignore = True
            break

    # 如果没有匹配忽略规则，直接返回 False
    if not matched_ignore:
        return False

    # 如果匹配了忽略规则，检查是否匹配否定规则
    for pattern in negation_patterns:
        if not pattern:
            continue
        pattern = pattern.strip().replace("\\", "/")
        if _match_pattern(path, pattern):
            return False

    # 匹配了忽略规则但没有匹配否定规则，返回 True
    return True


def get_project_root() -> Path:
    """
    获取项目根目录（向上查找包含 .gitignore 的目录）
    基于当前工作目录查找，而不是脚本所在目录

    Returns:
        项目根目录的 Path 对象
    """
    # 从当前工作目录开始，向上查找包含 .gitignore 的目录
    import os
    working_dir = Path(os.getcwd()).resolve()
    root_candidate = working_dir

    while root_candidate != root_candidate.parent:
        gitignore_path = root_candidate / ".gitignore"
        if gitignore_path.exists():
            return root_candidate
        root_candidate = root_candidate.parent

    # 如果找不到 .gitignore，返回当前工作目录作为项目根目录
    return working_dir
