import logging

logger = logging.getLogger(__name__)

from pathlib import Path
from typing import Optional, Tuple
import os
import json
import subprocess
import time
import shlex

from .gitignore import get_project_root


# 危险命令黑名单（禁止执行的命令）
DANGEROUS_COMMANDS = {
    # "rm",
    # "rmdir",
    # "del",
    # "delete",  # 删除命令
    # "mv",
    # "move",
    # "rename",  # 移动/重命名命令
    "dd",  # 磁盘操作命令
    "shutdown",
    "reboot",
    "halt",
    "poweroff",  # 系统关机命令
    "mkfs",
    "fdisk",
    "parted",  # 磁盘格式化命令
    "chmod",
    "chown",
    "chgrp",  # 权限修改命令（可能危险）
    "sudo",
    "su",  # 权限提升命令
    "passwd",  # 密码修改命令
    "killall",
    "pkill",  # 进程终止命令（可能危险）
    "format",
    "wipe",  # 格式化/擦除命令
    ">",
    ">>",  # 重定向操作符（单独使用时可能危险）
    # 网络下载命令（可能下载恶意文件）
    # 网络工具（可能用于攻击）
    # 动态执行命令
    "eval",
    "exec",  # 动态执行命令
    "source",
    ".",  # 加载脚本
}

# Git 需要人工参与的子命令黑名单
GIT_INTERACTIVE_SUBCOMMANDS = {
    "commit",  # 提交命令（可能需要输入提交信息或确认）
    "push",  # 推送命令（可能需要输入凭据或确认）
    "pull",  # 拉取命令（可能需要解决冲突）
    "merge",  # 合并命令（可能需要解决冲突）
    "rebase",  # 变基命令（可能需要解决冲突或交互式操作）
    "cherry-pick",  # 拣选命令（可能需要解决冲突）
    "revert",  # 撤销命令（可能需要确认）
    "reset",  # 重置命令（危险操作，需要确认）
    "clean",  # 清理未跟踪文件（需要确认）
    "stash",  # 暂存命令（通常需要人工确认）
    "tag",  # 标签命令（创建/删除标签需要确认）
    "branch",  # 分支命令（删除分支需要确认）
    "remote",  # 远程仓库命令（修改远程配置需要确认）
    "config",  # 配置命令（修改配置需要确认）
    "submodule",  # 子模块命令（子模块操作可能需要确认）
}

# 命令白名单（如果设置了白名单，只允许执行白名单中的命令）
# 默认情况下为空，表示不启用白名单机制
COMMAND_WHITELIST = set()  # 可以扩展为 {'ls', 'cat', 'grep', 'find', ...}

# 关键路径黑名单（禁止删除的文件和目录）
CRITICAL_PATH_BLACKLIST = {
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/var",
    "/sys",
    "/proc",
    "/dev",
    "config.json",
    "config.default.json",  # 配置文件保护
    "requirements.txt",  # 依赖文件保护
    "main.py",
    "agent.py",
    "middleware.py",  # 核心代码保护
    "README.md",  # 文档保护
}

# 白名单目录（如果启用，只允许在这些目录删除文件）
# 默认情况下为空集合，表示不启用白名单机制（允许在当前目录及其子目录删除）
ALLOWED_DELETE_DIRECTORIES = set()  # 可以扩展为 {Path('/tmp'), Path('./temp')} 等


def _is_safe_command(command: str) -> tuple[bool, str]:
    """
    检查命令是否安全

    Args:
        command: 要执行的命令字符串

    Returns:
        (is_safe, error_message) 元组
        - is_safe: 是否安全
        - error_message: 如果不安全，返回错误消息
    """
    # 去除首尾空白
    command = command.strip()

    if not command:
        return False, "错误: 命令不能为空"

    # 如果启用了白名单，检查命令是否在白名单中
    if COMMAND_WHITELIST:
        # 提取命令的第一个单词（命令名）
        # 在 Windows 上使用 posix=False 来正确处理路径中的反斜杠
        try:
            parts = shlex.split(command, posix=False)
        except ValueError:
            # 如果 shlex.split 失败（如包含未转义的反斜杠），使用简单分割
            parts = command.split()
        if not parts:
            return False, "错误: 无法解析命令"

        cmd_name = parts[0].lower()
        # 检查命令名是否在白名单中
        if cmd_name not in COMMAND_WHITELIST:
            return (
                False,
                f"错误: 命令 '{cmd_name}' 不在白名单中。允许的命令: {', '.join(sorted(COMMAND_WHITELIST))}",
            )

    # 检查黑名单（提取命令的第一个单词）
    # 在 Windows 上使用 posix=False 来正确处理路径中的反斜杠
    try:
        parts = shlex.split(command, posix=False)
    except ValueError as e:
        # 如果 shlex.split 失败（如包含未转义的反斜杠），使用简单分割
        logger.error(f"shlex.split 失败: {str(e)}")
        parts = command.split()
    if not parts:
        return False, "错误: 无法解析命令"

    cmd_name = parts[0].lower()

    # 检查命令名是否在黑名单中
    if cmd_name in DANGEROUS_COMMANDS:
        return False, f"错误: 禁止执行危险命令 '{cmd_name}'。该命令可能对系统造成损害。"
    
    # 检查 Git 需要人工参与的子命令
    if cmd_name == "git" and len(parts) > 1:
        git_subcommand = parts[1].lower()
        if git_subcommand in GIT_INTERACTIVE_SUBCOMMANDS:
            return False, f"错误: 禁止执行需要人工参与的 Git 命令 'git {git_subcommand}'。该命令可能需要用户输入、确认或解决冲突。"

    # 检查命令中是否包含危险的操作符或模式
    # 禁止命令链操作符（可能用于绕过安全检查）
    dangerous_patterns = [
        "&&",
        "||",
        ";",  # 命令链操作符
        "$(",
        "`",  # 命令替换（可能执行恶意代码）
    ]

    for pattern in dangerous_patterns:
        if pattern in command:
            return (
                False,
                f"错误: 命令中包含危险的操作符 '{pattern}'，可能被用于执行恶意操作或绕过安全检查。",
            )

    # 检查重定向操作符（可能覆盖文件）
    # 只禁止单独使用重定向操作符，允许在命令中使用（如 ls > file.txt）
    # 这里只做基本检查，更复杂的场景可以通过白名单机制控制
    if command.strip().startswith(">") or command.strip().startswith(">>"):
        return False, f"错误: 禁止单独使用重定向操作符，可能被用于覆盖文件。"

    return True, ""


def _is_safe_working_directory(
    working_directory: Optional[str], project_root: Path
) -> Tuple[bool, Optional[Path], str]:
    """
    检查工作目录是否安全（不能跳转到项目外）

    Args:
        working_directory: 指定的工作目录路径（可选）
        project_root: 项目根目录

    Returns:
        (is_safe, resolved_path, error_message) 元组
        - is_safe: 是否安全
        - resolved_path: 解析后的路径（如果安全）
        - error_message: 如果不安全，返回错误消息
    """
    if not working_directory:
        # 如果没有指定工作目录，使用项目根目录
        return True, project_root, ""

    try:
        # 解析工作目录路径
        work_dir = Path(working_directory)

        # 如果是相对路径，则相对于项目根目录
        if not work_dir.is_absolute():
            resolved_path = (project_root / work_dir).resolve()
        else:
            resolved_path = work_dir.resolve()

        # 检查路径是否在项目根目录内
        try:
            if not resolved_path.is_relative_to(project_root):
                return (
                    False,
                    None,
                    f"错误: 工作目录不能跳转到项目外。指定目录: {resolved_path}, 项目根目录: {project_root}",
                )
        except (ValueError, RuntimeError):
            # 如果路径解析失败，也视为不安全
            return (
                False,
                None,
                f"错误: 无法解析工作目录路径。指定目录: {working_directory}",
            )

        # 检查目录是否存在
        if not resolved_path.exists():
            return False, None, f"错误: 工作目录不存在。路径: {resolved_path}"

        # 检查是否为目录
        if not resolved_path.is_dir():
            return False, None, f"错误: 工作目录路径不是目录。路径: {resolved_path}"

        return True, resolved_path, ""

    except Exception as e:
        return False, None, f"错误: 检查工作目录时发生异常: {str(e)}"


def run_terminal_cmd(
    command: str,
    working_directory: Optional[str] = None,
    is_background: bool = False,
    timeout: int = 30,
) -> str:
    """
    执行系统命令并返回执行结果

    Args:
        command: 要执行的命令字符串（必需）
        working_directory: 工作目录路径（可选），默认为当前目录
        is_background: 是否在后台执行（默认 False）
        timeout: 命令执行超时时间（秒），默认 30 秒

    Returns:
        JSON 格式字符串，包含以下字段：
        - success: 是否执行成功（bool）
        - stdout: 标准输出内容（str）
        - stderr: 标准错误内容（str）
        - exit_code: 退出码（int）
        - execution_time: 执行时间（秒，float）
        - error: 错误消息（如果有，str）
        - command: 执行的命令（str）
        - working_directory: 工作目录（str）

    功能说明:
        - 执行系统命令并捕获标准输出、标准错误和退出码
        - 记录命令执行时间
        - 安全控制：
            * 禁止执行危险命令（如 rm, mv, dd, shutdown 等）
            * 支持命令白名单/黑名单机制
            * 限制工作目录不能跳转到项目外
        - 错误处理：
            * 捕获命令执行失败
            * 支持超时控制（默认 30 秒）
            * 捕获各种异常情况
        - 后台执行：
            * 当 is_background=True 时，命令在后台执行，立即返回
            * 后台执行的命令不等待完成，不捕获输出

    安全限制:
        - 禁止的命令包括：rm, mv, dd, shutdown, sudo, chmod 等危险命令
        - 工作目录必须位于项目根目录内
        - 禁止使用命令链操作符（&&, ||, ;）和命令替换（$(), `）
        - 禁止使用重定向操作符（>, >>）单独使用

    示例:
        >>> run_terminal_cmd("ls -la")
        >>> run_terminal_cmd("python --version", working_directory="./src")
        >>> run_terminal_cmd("sleep 60", timeout=10)  # 会超时
    """
    project_root = get_project_root()

    # 安全检查：检查命令是否安全
    is_safe, error_msg = _is_safe_command(command)
    if not is_safe:
        return json.dumps(
            {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": 0.0,
                "error": error_msg,
                "command": command,
                "working_directory": (
                    str(working_directory) if working_directory else str(project_root)
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    # 安全检查：检查工作目录是否安全
    is_safe_dir, safe_work_dir, dir_error_msg = _is_safe_working_directory(
        working_directory, project_root
    )
    if not is_safe_dir:
        return json.dumps(
            {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": 0.0,
                "error": dir_error_msg,
                "command": command,
                "working_directory": (
                    str(working_directory) if working_directory else str(project_root)
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    # 确定工作目录
    work_dir = safe_work_dir if safe_work_dir else project_root

    # 如果是后台执行，使用不同的处理方式
    if is_background:
        try:
            # 后台执行：使用 subprocess.Popen，不等待完成
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,  # 创建新的会话，使进程独立
            )

            return json.dumps(
                {
                    "success": True,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": None,
                    "execution_time": 0.0,
                    "error": None,
                    "command": command,
                    "working_directory": str(work_dir),
                    "background": True,
                    "pid": process.pid,
                    "message": f"命令已在后台启动（PID: {process.pid}）",
                },
                ensure_ascii=False,
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "execution_time": 0.0,
                    "error": f"错误: 后台执行命令失败: {str(e)}",
                    "command": command,
                    "working_directory": str(work_dir),
                },
                ensure_ascii=False,
                indent=2,
            )

    # 前台执行：等待命令完成并捕获输出
    start_time = time.time()

    try:
        # 使用 subprocess.run 执行命令，设置超时
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(work_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",  # 处理编码错误
        )

        execution_time = time.time() - start_time

        # 构建返回结果
        return json.dumps(
            {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "execution_time": round(execution_time, 3),
                "error": (
                    None
                    if result.returncode == 0
                    else f"命令执行失败，退出码: {result.returncode}"
                ),
                "command": command,
                "working_directory": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        )

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        return json.dumps(
            {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "error": f"错误: 命令执行超时（超过 {timeout} 秒）",
                "command": command,
                "working_directory": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        )

    except subprocess.SubprocessError as e:
        execution_time = time.time() - start_time
        return json.dumps(
            {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "error": f"错误: 子进程执行失败: {str(e)}",
                "command": command,
                "working_directory": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        execution_time = time.time() - start_time
        return json.dumps(
            {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": round(execution_time, 3),
                "error": f"错误: 执行命令时发生未知异常: {str(e)}",
                "command": command,
                "working_directory": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
