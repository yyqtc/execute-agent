from pathlib import Path
from typing import Optional
from tools.gitignore import load_gitignore_patterns, is_path_ignored, get_project_root

import os
import logging

logger = logging.getLogger(__name__)


def format_error(
    message: str, details: Optional[str] = None, path: Optional[str] = None
) -> str:
    """
    统一格式化错误消息

    Args:
        message: 主要错误消息
        details: 详细错误信息（可选）
        path: 相关文件路径（可选）

    Returns:
        格式化的错误消息字符串
    """
    error_parts = [f"错误: {message}"]

    if path:
        error_parts.append(f"路径: {path}")

    if details:
        error_parts.append(f"详情: {details}")

    return "，".join(error_parts)


def _write_file_impl(
    file_path: str, content: str, file_writer: Optional[object] = None, overwrite: bool = True
) -> str:
    """
    写入文件的内部实现函数

    Args:
        file_path: 文件路径（字符串）
        content: 要写入的内容（字符串）
        file_writer: SafeFileWriter 实例（可选）

    Returns:
        操作结果消息字符串
    """
    try:
        # 尝试导入 SafeFileWriter（如果可用）
        try:
            from main import SafeFileWriter
        except ImportError:
            SafeFileWriter = None

        # 如果提供了 file_writer，使用其 write 方法
        if file_writer is not None and SafeFileWriter is not None:
            try:
                # 使用 SafeFileWriter 的 write 方法（它会进行安全检查）
                if overwrite:
                    success = file_writer.write(file_path, content)
                else:
                    success = file_writer.append(file_path, content)
                if success:
                    return f"成功写入文件: {file_path} (共 {len(content)} 字符)"
                else:
                    # print_mode 模式下，SafeFileWriter.write 返回 False
                    return (
                        f"[打印模式] 建议写入文件: {file_path} (共 {len(content)} 字符)"
                    )
            except ValueError as e:
                # SafeFileWriter 会抛出 ValueError 如果路径不安全
                return format_error(str(e), path=file_path)
            except Exception as e:
                return format_error(
                    "使用 SafeFileWriter 写入失败", details=str(e), path=file_path
                )

        # 如果没有提供 file_writer，直接进行安全写入
        path = Path(file_path)

        # 获取当前工作目录（确保路径操作在当前目录范围内）
        current_dir = Path.cwd().resolve()

        # 解析目标路径（如果是相对路径，则相对于当前目录）
        if path.is_absolute():
            resolved_path = path.resolve()
        else:
            resolved_path = (current_dir / path).resolve()

        # 安全检查：确保路径在当前目录或其子目录中
        try:
            # 检查路径是否在当前目录内
            if not resolved_path.is_relative_to(current_dir):
                return f"错误: 不允许写入父目录。目标路径: {resolved_path}, 当前目录: {current_dir}"
        except (ValueError, RuntimeError):
            # 如果路径解析失败，也视为不安全
            return f"错误: 路径解析失败，可能不安全。目标路径: {file_path}"

        # 确保父目录存在
        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            return f"错误: 权限不足，无法创建目录。路径: {resolved_path.parent}, 错误: {str(e)}"
        except Exception as e:
            return f"错误: 创建目录失败。路径: {resolved_path.parent}, 错误: {str(e)}"

        # 检查写入权限
        if resolved_path.exists() and not os.access(resolved_path, os.W_OK):
            return f"错误: 没有写入权限。路径: {resolved_path}"

        # 写入文件（使用 UTF-8 编码）
        try:
            if overwrite:
                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(resolved_path, "a", encoding="utf-8") as f:
                    f.write(content)

            return f"成功写入文件: {resolved_path} (共 {len(content)} 字符)"
        except UnicodeEncodeError as e:
            return f"错误: 内容编码错误，无法使用 UTF-8 编码。路径: {resolved_path}, 错误: {str(e)}"
        except IOError as e:
            return f"错误: 写入文件失败。路径: {resolved_path}, 错误: {str(e)}"
        except OSError as e:
            return f"错误: 操作系统错误，无法写入文件。路径: {resolved_path}, 错误: {str(e)}"

    except PermissionError as e:
        return f"错误: 权限不足，无法访问路径。路径: {file_path}, 错误: {str(e)}"
    except Exception as e:
        return f"错误: 写入文件时发生未知错误。路径: {file_path}, 错误: {str(e)}"


def read_file(
    file_path: str,
    encoding: str = "utf-8",
    chunk_size: int = 8192,
    stream: bool = False,
):
    """
    读取指定路径的文件内容，支持一次性读取和流式读取两种模式。

    Args:
        file_path: 文件路径（字符串，支持相对或绝对路径）
        encoding: 文件编码，默认为 'utf-8'
        chunk_size: 每次读取的块大小（字节），默认为8KB，仅在 stream=True 时生效
        stream: 是否以生成器方式流式返回内容，默认为 False

    Returns:
        若 stream=False，返回完整文件内容字符串；
        若 stream=True，返回一个生成器，每次产出一个文本块

    功能说明:
        - 使用指定编码（默认UTF-8）读取文件
        - 支持流式读取以处理超大文件，避免内存溢出
        - 在非流式模式下，内部使用列表收集并拼接以避免 O(n²) 字符串拼接问题
        - 处理文件不存在、权限不足、读取失败等异常
    """
    try:
        # 将路径转换为 Path 对象
        path = Path(file_path)

        # 检查文件是否存在
        if not path.exists():
            return format_error("文件不存在", path=file_path)

        # 检查是否为文件（而非目录）
        if not path.is_file():
            return format_error("路径不是文件", path=file_path)

        # 检查读取权限
        if not os.access(path, os.R_OK):
            return format_error("没有读取权限", path=file_path)

        # 流式读取模式
        if stream:

            def _stream_reader():
                try:
                    with open(path, "r", encoding=encoding) as f:
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            yield chunk
                except UnicodeDecodeError as e:
                    yield f"错误: 文件编码错误，无法使用 {encoding} 解码。路径: {file_path}, 错误: {str(e)}"
                except IOError as e:
                    yield f"错误: 读取文件失败。路径: {file_path}, 错误: {str(e)}"

            return _stream_reader()

        # 非流式模式：完整读取
        chunks = []
        try:
            with open(path, "r", encoding=encoding) as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
            return "".join(chunks)
        except UnicodeDecodeError as e:
            return f"错误: 文件编码错误，无法使用 {encoding} 解码。路径: {file_path}, 错误: {str(e)}"
        except IOError as e:
            return f"错误: 读取文件失败。路径: {file_path}, 错误: {str(e)}"

    except PermissionError as e:
        return f"错误: 权限不足，无法访问文件。路径: {file_path}, 错误: {str(e)}"
    except Exception as e:
        return f"错误: 读取文件时发生未知错误。路径: {file_path}, 错误: {str(e)}"


def write_file(
    file_path: str, content: str, file_writer: Optional[object] = None, overwrite: bool = True
) -> str:
    """
    写入文件内容，集成 SafeFileWriter

    Args:
        file_path: 文件路径（字符串）
        content: 要写入的内容（字符串）
        file_writer: SafeFileWriter 实例（可选）

    Returns:
        操作结果消息字符串

    功能说明:
        - 若提供 file_writer，则调用其 write 方法并做安全检查
        - 若未提供，则直接写入（仍需处理异常）
        - 处理路径不安全、写入失败、编码错误等异常
        - 确保所有路径操作在当前目录范围内，不对父目录进行写入操作
    """
    return _write_file_impl(file_path, content, file_writer, overwrite)


def edit_file(
    file_path: str, old_string: str, new_string: str, replace_all: bool = False
) -> str:
    """
    编辑文件内容，精确匹配并替换指定字符串

    Args:
        file_path: 文件路径（字符串，支持相对或绝对路径）
        old_string: 要替换的旧字符串（支持多行）
        new_string: 替换后的新字符串（支持多行）
        replace_all: 是否替换所有匹配项，默认为 False（只替换第一个匹配项）

    Returns:
        操作结果消息字符串；若出错返回错误消息

    功能说明:
        - 精确匹配 old_string，保持代码格式和缩进
        - 支持多行替换和上下文匹配
        - 当 replace_all=False 时，如果 old_string 不唯一会提示错误
        - 处理文件不存在、权限不足、替换失败等异常
        - 使用 UTF-8 编码读写文件
    """
    try:
        # 将路径转换为 Path 对象
        path = Path(file_path)

        # 获取当前工作目录（确保路径操作在当前目录范围内）
        current_dir = Path.cwd().resolve()

        # 解析目标路径（如果是相对路径，则相对于当前目录）
        if path.is_absolute():
            resolved_path = path.resolve()
        else:
            resolved_path = (current_dir / path).resolve()

        # 安全检查：确保路径在当前目录或其子目录中
        try:
            # 检查路径是否在当前目录内
            if not resolved_path.is_relative_to(current_dir):
                return f"错误: 不允许编辑父目录中的文件。目标路径: {resolved_path}, 当前目录: {current_dir}"
        except (ValueError, RuntimeError):
            # 如果路径解析失败，也视为不安全
            return f"错误: 路径解析失败，可能不安全。目标路径: {file_path}"

        # 检查文件是否存在
        if not resolved_path.exists():
            return format_error("文件不存在", path=file_path)

        # 检查是否为文件（而非目录）
        if not resolved_path.is_file():
            return format_error("路径不是文件", path=file_path)

        # 检查读取权限
        if not os.access(resolved_path, os.R_OK):
            return format_error("没有读取权限", path=file_path)

        # 检查写入权限
        if not os.access(resolved_path, os.W_OK):
            return format_error("没有写入权限", path=file_path)

        # 读取文件内容（使用 UTF-8 编码）
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError as e:
            return f"错误: 文件编码错误，无法使用 UTF-8 解码。路径: {file_path}, 错误: {str(e)}"
        except IOError as e:
            return f"错误: 读取文件失败。路径: {file_path}, 错误: {str(e)}"

        # 检查 old_string 是否在文件中存在
        if old_string not in content:
            return f"错误: 未找到要替换的字符串。路径: {file_path}"

        # 计算 old_string 出现的次数
        count = content.count(old_string)

        # 如果 replace_all=False，检查 old_string 是否唯一
        if not replace_all:
            if count > 1:
                return f"错误: old_string 在文件中出现 {count} 次，不是唯一的。请设置 replace_all=True 来替换所有匹配项，或者提供更具体的上下文来唯一标识要替换的位置。路径: {file_path}"

        # 执行替换
        try:
            if replace_all:
                # 替换所有匹配项
                new_content = content.replace(old_string, new_string)
                replaced_count = count
            else:
                # 只替换第一个匹配项
                new_content = content.replace(old_string, new_string, 1)
                replaced_count = 1

            # 检查替换是否成功（内容应该发生变化）
            if new_content == content:
                return f"错误: 替换失败，文件内容未发生变化。路径: {file_path}"

            # 写回文件（使用 UTF-8 编码）
            try:
                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                if replace_all:
                    return f"成功替换文件内容: {file_path} (共替换 {replaced_count} 处)"
                else:
                    return f"成功替换文件内容: {file_path} (替换了第 1 处匹配)"
            except UnicodeEncodeError as e:
                return f"错误: 内容编码错误，无法使用 UTF-8 编码。路径: {file_path}, 错误: {str(e)}"
            except IOError as e:
                return f"错误: 写入文件失败。路径: {file_path}, 错误: {str(e)}"
            except OSError as e:
                return f"错误: 操作系统错误，无法写入文件。路径: {file_path}, 错误: {str(e)}"

        except Exception as e:
            return f"错误: 替换操作失败。路径: {file_path}, 错误: {str(e)}"

    except PermissionError as e:
        return f"错误: 权限不足，无法访问文件。路径: {file_path}, 错误: {str(e)}"
    except Exception as e:
        return f"错误: 编辑文件时发生未知错误。路径: {file_path}, 错误: {str(e)}"


def delete_file(file_path: str) -> str:
    """
    删除指定文件（带安全检查）

    Args:
        file_path: 要删除的文件路径（字符串，支持相对或绝对路径）

    Returns:
        操作结果消息字符串；若出错返回错误消息

    功能说明:
        - 执行严格的安全检查，确保不会误删关键文件
        - 处理文件不存在、权限不足、删除失败等异常
        - 确保所有路径操作在当前目录范围内，不对父目录进行删除操作

    安全限制:
        - 禁止删除黑名单中的关键路径（系统目录、配置文件、核心代码等）
        - 支持白名单目录限制（如果启用）
        - 检查文件存在性和权限
        - 确保路径在当前项目目录内，不允许删除父目录中的文件
    """
    from tools.command import CRITICAL_PATH_BLACKLIST, ALLOWED_DELETE_DIRECTORIES

    try:
        # 将路径转换为 Path 对象
        path = Path(file_path)

        # 获取当前工作目录（确保路径操作在当前目录范围内）
        current_dir = Path.cwd().resolve()

        # 解析目标路径（如果是相对路径，则相对于当前目录）
        if path.is_absolute():
            resolved_path = path.resolve()
        else:
            resolved_path = (current_dir / path).resolve()

        # 安全检查1：确保路径在当前目录或其子目录中
        try:
            # 检查路径是否在当前目录内
            if not resolved_path.is_relative_to(current_dir):
                return f"错误: 不允许删除父目录中的文件。目标路径: {resolved_path}, 当前目录: {current_dir}"
        except (ValueError, RuntimeError):
            # 如果路径解析失败，也视为不安全
            return f"错误: 路径解析失败，可能不安全。目标路径: {file_path}"

        # 安全检查2：检查关键路径黑名单
        path_str = str(resolved_path)
        path_normalized = path_str.replace("\\", "/")  # 统一路径分隔符

        for blacklisted in CRITICAL_PATH_BLACKLIST:
            blacklisted_normalized = blacklisted.replace("\\", "/")
            # 检查路径是否包含黑名单项或以黑名单项结尾
            if blacklisted_normalized in path_normalized or path_normalized.endswith(
                blacklisted_normalized
            ):
                return f"错误: 禁止删除关键路径。路径: {file_path}"

        # 安全检查3：白名单目录限制（如果启用）
        if ALLOWED_DELETE_DIRECTORIES:
            parent_dir = resolved_path.parent.resolve()
            is_allowed = False
            for allowed_dir in ALLOWED_DELETE_DIRECTORIES:
                allowed_path = Path(allowed_dir).resolve()
                try:
                    if parent_dir.is_relative_to(allowed_path):
                        is_allowed = True
                        break
                except (ValueError, RuntimeError):
                    continue

            if not is_allowed:
                return f"错误: 文件不在允许删除的目录中。路径: {file_path}"

        # 安全检查4：文件存在性检查
        if not resolved_path.exists():
            return f"错误: 文件不存在。路径: {file_path}"

        # 安全检查5：确保是文件而非目录
        if not resolved_path.is_file():
            return f"错误: 路径不是文件。路径: {file_path}"

        # 安全检查6：权限检查
        if not os.access(resolved_path, os.W_OK):
            return f"错误: 没有删除权限。路径: {file_path}"

        # 执行删除
        try:
            resolved_path.unlink()
            return f"成功删除文件: {file_path}"
        except PermissionError as e:
            return f"错误: 权限不足，无法删除文件。路径: {file_path}, 错误: {str(e)}"
        except OSError as e:
            return f"错误: 删除文件失败。路径: {file_path}, 错误: {str(e)}"

    except PermissionError as e:
        return f"错误: 权限不足，无法访问路径。路径: {file_path}, 错误: {str(e)}"
    except Exception as e:
        return f"错误: 删除文件时发生未知错误。路径: {file_path}, 错误: {str(e)}"


def list_directory(directory_path: str = ".", recursive: bool = False) -> list:
    """
    列出指定目录的内容。

    Args:
        directory_path: 要列出的目录路径，默认为当前目录（"."）
        recursive: 是否递归列出所有子目录内容，默认为 False

    Returns:
        包含目录内容的列表。每个元素为文件或目录的路径字符串。
        如果目录不存在或发生错误，返回包含错误信息的列表。

    功能说明:
        - 默认列出指定目录的直接子项（文件和子目录）
        - 当 recursive 为 True 时，递归列出所有子目录的内容
        - 使用 os 标准库进行目录操作
        - 返回的路径为相对于 directory_path 的路径（非递归模式）或绝对路径（递归模式）
        - 自动读取并解析 .gitignore 文件中的排除规则，过滤匹配的条目
    """
    try:
        # 解析目录路径
        dir_path = os.path.abspath(directory_path)

        # 检查目录是否存在
        if not os.path.exists(dir_path):
            return [f"错误: 目录不存在。路径: {directory_path}"]

        # 检查是否为目录
        if not os.path.isdir(dir_path):
            return [f"错误: 路径不是目录。路径: {directory_path}"]

        # 检查读取权限
        if not os.access(dir_path, os.R_OK):
            return [f"错误: 没有读取权限。路径: {directory_path}"]

        # 确定项目根目录：向上查找包含 .gitignore 的目录
        project_root = get_project_root()

        # 从项目根目录统一读取 .gitignore
        ignore_patterns, negation_patterns = load_gitignore_patterns(str(project_root))

        result = []

        if recursive:
            # 递归列出所有子目录内容
            for root, dirs, files in os.walk(dir_path):
                # 创建相对于项目根目录的路径用于匹配
                rel_root = os.path.relpath(root, str(project_root))
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
                # 添加目录路径（如果未被忽略）
                if not is_path_ignored(
                    rel_root if rel_root else "", ignore_patterns, negation_patterns
                ):
                    result.append(root)
                # 添加文件路径
                for file in files:
                    file_rel_path = os.path.join(rel_root, file) if rel_root else file
                    if not is_path_ignored(
                        file_rel_path, ignore_patterns, negation_patterns
                    ):
                        file_path = os.path.join(root, file)
                        result.append(file_path)
        else:
            # 只列出直接子项
            try:
                items = os.listdir(dir_path)
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    # 创建相对于项目根目录的路径用于匹配
                    rel_item_path = os.path.relpath(item_path, str(project_root))
                    if not is_path_ignored(
                        rel_item_path, ignore_patterns, negation_patterns
                    ):
                        result.append(item_path)
            except PermissionError:
                return [f"错误: 权限不足，无法列出目录内容。路径: {directory_path}"]

        return result

    except PermissionError as e:
        return [f"错误: 权限不足，无法访问目录。路径: {directory_path}, 错误: {str(e)}"]
    except Exception as e:
        return [f"错误: 列出目录时发生未知错误。路径: {directory_path}, 错误: {str(e)}"]
