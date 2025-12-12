from tools.command import run_terminal_cmd as run_terminal_cmd_impl
from typing import Optional

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

    return run_terminal_cmd_impl(command, working_directory, is_background, timeout)
