import logging

logger = logging.getLogger(__name__)
import re
from pathlib import Path
from typing import List, Tuple, Optional


def extract_paths_from_text(text: str) -> List[str]:
    """
    从用户输入文本中提取 @ 符号后的路径。

    支持以下格式：
    - @path/to/file
    - @"path with spaces.txt"
    - 多个 @ 符号：@file1.txt @file2.txt
    - 混合引号和非引号：@normal.txt @"spaced path".txt

    Args:
        text (str): 用户输入的原始文本

    Returns:
        List[str]: 提取到的路径列表
    """
    if not isinstance(text, str):
        return []

    paths = []
    i = 0
    n = len(text)

    while i < n:
        # 查找 @ 符号
        if text[i] == "@":
            i += 1  # 跳过 @

            # 跳过前导空白
            while i < n and text[i].isspace():
                i += 1

            if i >= n:
                break

            # 判断是否以引号开始
            if i < n and text[i] in "\"'":
                quote_char = text[i]
                i += 1  # 跳过引号
                start = i

                # 寻找结束引号
                while i < n and text[i] != quote_char:
                    i += 1

                if i < n and text[i] == quote_char:
                    # 成功找到闭合引号
                    path = text[start:i]
                    paths.append(path)
                    i += 1  # 跳过结束引号
                else:
                    # 未找到闭合引号，视为无效
                    pass
            else:
                # 非引号路径，读取到空白或字符串结束
                start = i
                while i < n and not text[i].isspace():
                    i += 1
                path = text[start:i]
                if path:  # 确保不是空字符串
                    paths.append(path)

        else:
            i += 1

    return paths


def validate_and_classify_path(path_str: str) -> Tuple[bool, str, Optional[str]]:
    """
    验证路径是否存在，并判断其类型（文件/目录）。

    Args:
        path_str (str): 要验证的路径字符串

    Returns:
        Tuple[bool, str, Optional[str]]:
            (是否成功, 类型描述, 错误信息)
            类型描述: 'file', 'directory', 或 'invalid'
    """
    try:
        path = Path(path_str)

        if not path.exists():
            return False, "invalid", f"路径 '{path_str}' 不存在"

        if path.is_file():
            return True, "file", None

        if path.is_dir():
            return True, "directory", None

        return False, "invalid", f"'{path_str}' 不是有效的文件或目录"

    except Exception as e:
        logging.error(f"验证路径时发生错误: {str(e)}")
        return False, "invalid", f"验证路径时发生错误: {str(e)}"


def read_file_content(file_path: str) -> Tuple[bool, str]:
    """
    安全读取文件内容。

    Args:
        file_path (str): 文件路径

    Returns:
        Tuple[bool, str]: (是否成功, 内容或错误信息)
    """
    try:
        path = Path(file_path)

        # 再次确认是文件
        if not path.is_file():
            return False, f"'{file_path}' 不是文件"

        content = path.read_text(encoding="utf-8")
        return True, content

    except UnicodeDecodeError:
        return False, f"无法解码文件 '{file_path}'，可能不是文本文件"
    except PermissionError:
        return False, f"没有权限读取文件 '{file_path}'"
    except Exception as e:
        return False, f"读取文件时发生错误: {str(e)}"


def process_at_paths(input_text: str) -> str:
    """
    处理包含 @ 路径的用户输入，将每个 @path 替换为带标记的文件内容块。

    Args:
        input_text (str): 用户输入文本

    Returns:
        str: 替换后的文本
    """
    if not input_text or not isinstance(input_text, str):
        return "请输入有效文本。"

    # 提取所有 @ 后的路径
    paths = extract_paths_from_text(input_text)

    result_text = input_text

    for path_str in paths:
        success, path_type, error_msg = validate_and_classify_path(path_str)

        if not success:
            # 替换为错误信息
            replacement = f"--- ERROR: {error_msg} ---"
            old_ref = f"@{path_str}"
            if old_ref in result_text:
                result_text = result_text.replace(old_ref, replacement)

        if path_type == "file":
            file_success, content = read_file_content(path_str)
            if file_success:
                # 构造替换内容
                replacement = (
                    f"--- BEGIN FILE: {path_str} ---\n{content}\n--- END FILE ---"
                )
                # 安全替换：仅替换完整的 @path_str，避免子串误替换
                old_ref = f"@{path_str}"
                if old_ref in result_text:
                    result_text = result_text.replace(old_ref, replacement)
            else:
                # 读取失败，替换为错误信息
                replacement = f"--- ERROR: {content} ---"
                old_ref = f"@{path_str}"
                if old_ref in result_text:
                    result_text = result_text.replace(old_ref, replacement)

        elif path_type == "directory":
            from .utils import display_folder_content

            folder_content = display_folder_content(path_str)
            replacement = f"--- BEGIN DIRECTORY: {path_str} ---\n{folder_content}\n--- END DIRECTORY ---"
            # 安全替换：仅当完整匹配时才替换
            old_ref = f"@{path_str}"
            if old_ref in result_text:
                result_text = result_text.replace(old_ref, replacement)

    return result_text
