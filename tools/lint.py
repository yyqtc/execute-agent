import logging

logger = logging.getLogger(__name__)

from pathlib import Path
from typing import List, Optional, Tuple
import subprocess
import json

from .gitignore import get_project_root


def _parse_pylint_output(output: str, file_path: Optional[str]) -> List[dict]:
    """
    解析 pylint 的输出

    Args:
        output: pylint 的标准输出
        file_path: 文件路径（如果为 None，则从输出中提取）

    Returns:
        错误列表，每个元素包含 file_path, line_number, error_type, message
    """
    errors = []
    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue

        # pylint 输出格式: file_path:line_number:column: error_type: message
        # 例如: example.py:123:4: C0103: Invalid name "foo" (should match [a-z_][a-z0-9_]*)
        parts = line.split(":", 3)
        if len(parts) >= 4:
            try:
                # 如果 file_path 为 None，从输出中提取文件路径
                error_file_path = file_path if file_path else parts[0]
                line_num = int(parts[1])
                error_type = parts[2].strip()
                message = parts[3].strip()

                errors.append(
                    {
                        "file_path": error_file_path,
                        "line_number": line_num,
                        "error_type": error_type,
                        "message": message,
                    }
                )
            except (ValueError, IndexError):
                continue

    return errors


def _parse_flake8_output(output: str, file_path: Optional[str]) -> List[dict]:
    """
    解析 flake8 的输出

    Args:
        output: flake8 的标准输出
        file_path: 文件路径（如果为 None，则从输出中提取）

    Returns:
        错误列表，每个元素包含 file_path, line_number, error_type, message
    """
    errors = []
    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue

        # flake8 输出格式: file_path:line_number:column: error_code message
        # 例如: example.py:123:4: E302 expected 2 blank lines
        parts = line.split(":", 3)
        if len(parts) >= 4:
            try:
                # 如果 file_path 为 None，从输出中提取文件路径
                error_file_path = file_path if file_path else parts[0]
                line_num = int(parts[1])
                error_code_and_message = parts[3].strip()
                # 分离错误代码和消息
                error_parts = error_code_and_message.split(" ", 1)
                error_type = error_parts[0] if error_parts else "UNKNOWN"
                message = (
                    error_parts[1] if len(error_parts) > 1 else error_code_and_message
                )

                errors.append(
                    {
                        "file_path": error_file_path,
                        "line_number": line_num,
                        "error_type": error_type,
                        "message": message,
                    }
                )
            except (ValueError, IndexError):
                continue

    return errors


def _parse_mypy_output(output: str, file_path: Optional[str]) -> List[dict]:
    """
    解析 mypy 的输出

    Args:
        output: mypy 的标准输出
        file_path: 文件路径（如果为 None，则从输出中提取）

    Returns:
        错误列表，每个元素包含 file_path, line_number, error_type, message
    """
    errors = []
    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue

        # mypy 输出格式: file_path:line_number: error_type: message
        # 例如: example.py:123: error: Incompatible types in assignment
        parts = line.split(":", 2)
        if len(parts) >= 3:
            try:
                # 如果 file_path 为 None，从输出中提取文件路径
                error_file_path = file_path if file_path else parts[0]
                line_num = int(parts[1])
                error_type_and_message = parts[2].strip()
                # 分离错误类型和消息
                error_parts = error_type_and_message.split(":", 1)
                error_type = error_parts[0].strip() if error_parts else "error"
                message = (
                    error_parts[1].strip()
                    if len(error_parts) > 1
                    else error_type_and_message
                )

                errors.append(
                    {
                        "file_path": error_file_path,
                        "line_number": line_num,
                        "error_type": error_type,
                        "message": message,
                    }
                )
            except (ValueError, IndexError):
                continue

    return errors


def _run_linter(
    linter_type: str, file_path: Optional[str], project_root: Path
) -> Tuple[List[dict], dict]:
    """
    运行指定的 linter

    Args:
        linter_type: linter 类型 ('pylint', 'flake8', 'mypy')
        file_path: 文件路径（可选，如果为 None 则检查整个项目）
        project_root: 项目根目录

    Returns:
        (errors, stats) 元组
        - errors: 错误列表
        - stats: 统计信息字典
    """
    errors = []
    stats = {
        "linter_type": linter_type,
        "file_path": file_path,
        "total_errors": 0,
        "error_types": {},
        "success": False,
        "error_message": None,
    }

    # 确定要检查的文件或目录
    if file_path:
        # 检查单个文件
        path = Path(file_path)
        if not path.is_absolute():
            resolved_path = (project_root / path).resolve()
        else:
            resolved_path = path.resolve()

        # 安全检查：确保路径在项目根目录内
        try:
            if not resolved_path.is_relative_to(project_root):
                stats["error_message"] = (
                    f"错误: 不允许检查父目录中的文件。目标路径: {resolved_path}, 项目根目录: {project_root}"
                )
                return errors, stats
        except (ValueError, RuntimeError):
            stats["error_message"] = (
                f"错误: 路径解析失败，可能不安全。目标路径: {file_path}"
            )
            return errors, stats

        if not resolved_path.exists():
            stats["error_message"] = f"错误: 文件不存在。路径: {file_path}"
            return errors, stats

        if not resolved_path.is_file():
            stats["error_message"] = f"错误: 路径不是文件。路径: {file_path}"
            return errors, stats

        target = str(resolved_path)
    else:
        # 检查整个项目
        target = str(project_root)

    # 构建 linter 命令
    linter_commands = {
        "pylint": ["pylint", "--output-format=text", target],
        "flake8": ["flake8", target],
        "mypy": ["mypy", "--show-error-codes", target],
    }

    if linter_type not in linter_commands:
        stats["error_message"] = (
            f"错误: 不支持的 linter 类型 '{linter_type}'。支持的 linter: pylint, flake8, mypy"
        )
        return errors, stats

    command = linter_commands[linter_type]

    # 执行 linter 命令
    try:
        result = subprocess.run(
            command,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,  # 60 秒超时
            encoding="utf-8",
            errors="replace",
        )

        # 解析输出
        output = result.stdout + result.stderr

        # 根据 linter 类型解析输出
        # 如果指定了 file_path，使用它；否则为 None，让解析函数从输出中提取
        parse_file_path = file_path if file_path else None
        if linter_type == "pylint":
            errors = _parse_pylint_output(output, parse_file_path)
        elif linter_type == "flake8":
            errors = _parse_flake8_output(output, parse_file_path)
        elif linter_type == "mypy":
            errors = _parse_mypy_output(output, parse_file_path)

        # 统计错误类型
        error_types = {}
        for error in errors:
            error_type = error.get("error_type", "UNKNOWN")
            error_types[error_type] = error_types.get(error_type, 0) + 1

        stats["total_errors"] = len(errors)
        stats["error_types"] = error_types
        stats["success"] = True

        # 如果命令失败但没有解析到错误，可能是 linter 未安装或其他问题
        if result.returncode != 0 and not errors:
            # 检查是否是 linter 未安装
            if "command not found" in output.lower() or "not found" in output.lower():
                stats["error_message"] = (
                    f"错误: {linter_type} 未安装或不在 PATH 中。请先安装 {linter_type}。"
                )
            else:
                stats["error_message"] = (
                    f"错误: {linter_type} 执行失败。退出码: {result.returncode}\n输出: {output[:500]}"
                )

    except subprocess.TimeoutExpired:
        stats["error_message"] = f"错误: {linter_type} 执行超时（超过 60 秒）"
    except FileNotFoundError:
        stats["error_message"] = (
            f"错误: {linter_type} 未安装或不在 PATH 中。请先安装 {linter_type}。"
        )
    except Exception as e:
        stats["error_message"] = f"错误: 执行 {linter_type} 时发生异常: {str(e)}"

    return errors, stats


def read_lints(file_path: Optional[str] = None, linter_type: str = "pylint") -> str:
    """
    读取指定文件或目录的 linter 错误

    Args:
        file_path: 文件路径（可选），如果未提供则检查整个项目
        linter_type: linter 类型，可选值: "pylint", "flake8", "mypy"，默认为 "pylint"

    Returns:
        JSON 格式字符串，包含以下字段：
        - errors: 错误列表，每个元素包含：
            * file_path: 文件路径
            * line_number: 行号
            * error_type: 错误类型（如 "E302", "C0103", "error" 等）
            * message: 错误消息
        - stats: 统计信息字典，包含：
            * linter_type: 使用的 linter 类型
            * file_path: 检查的文件路径（如果指定）
            * total_errors: 总错误数
            * error_types: 按错误类型分组的统计（字典）
            * success: 是否成功执行
            * error_message: 错误消息（如果有）

    功能说明:
        - 支持多种 linter：pylint、flake8、mypy
        - 可以检查单个文件或整个项目
        - 自动解析 linter 输出并提取错误信息
        - 提供详细的错误统计信息
        - 确保路径安全检查，不允许检查父目录中的文件

    示例:
        >>> read_lints("example.py", "pylint")
        >>> read_lints("example.py", "flake8")
        >>> read_lints(linter_type="mypy")  # 检查整个项目
    """
    project_root = get_project_root()

    # 验证 linter_type
    supported_linters = ["pylint", "flake8", "mypy"]
    if linter_type not in supported_linters:
        return json.dumps(
            {
                "errors": [],
                "stats": {
                    "linter_type": linter_type,
                    "file_path": file_path,
                    "total_errors": 0,
                    "error_types": {},
                    "success": False,
                    "error_message": f"错误: 不支持的 linter 类型 '{linter_type}'。支持的 linter: {', '.join(supported_linters)}",
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    # 运行 linter
    errors, stats = _run_linter(linter_type, file_path, project_root)

    # 返回结果
    result = {"errors": errors, "stats": stats}

    return json.dumps(result, ensure_ascii=False, indent=2)
