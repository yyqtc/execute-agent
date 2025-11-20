"""
文件和文件夹内容显示工具
提供 display_folder_content 函数用于展示指定路径下的内容。
"""

import logging

logger = logging.getLogger(__name__)

from pathlib import Path


def display_folder_content(path: str = ".", show_hidden: bool = False) -> str:
    """
    显示指定路径下的文件夹和文件内容。

    Args:
        path (str): 要显示内容的路径，默认为当前目录
        show_hidden (bool): 是否显示隐藏文件，默认为 False

    Returns:
        str: 格式化的目录内容字符串
    """
    # 创建 Path 对象
    folder_path = Path(path)

    # 检查路径是否存在
    if not folder_path.exists():
        return f"错误: 路径 '{path}' 不存在"

    # 检查路径是否为目录
    if not folder_path.is_dir():
        return f"错误: '{path}' 不是有效的目录"

    # 获取目录内容
    try:
        items = list(folder_path.iterdir())

        # 过滤隐藏文件（如果不需要显示）
        if not show_hidden:
            items = [item for item in items if not item.name.startswith(".")]

        # 按名称排序
        items.sort(key=lambda x: x.name.lower())

        # 构建输出字符串
        result_lines = [f"内容 of '{folder_path}':"]

        for item in items:
            if item.is_dir():
                result_lines.append(f"[D] {item.name}/")
            else:
                result_lines.append(f"[F] {item.name}")

        if not result_lines[1:]:  # 如果除了标题外没有其他内容
            result_lines.append("(空目录)")

        return "\n".join(result_lines)

    except PermissionError:
        return f"错误: 没有权限访问 '{path}'"
    except Exception as e:
        return f"错误: 读取目录时发生异常: {str(e)}"
