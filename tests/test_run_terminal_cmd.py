#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_terminal_cmd 工具的单元测试
验证命令执行、安全控制、超时处理和后台执行功能
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
import json
import subprocess
import time
import shlex
from pathlib import Path
from typing import Optional, Tuple

# 为了避免循环导入问题，直接复制 run_terminal_cmd 函数及其依赖函数的实现
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

# 命令白名单（如果设置了白名单，只允许执行白名单中的命令）
COMMAND_WHITELIST = set()


def _get_project_root() -> Path:
    """获取项目根目录"""
    # 在测试中，使用当前工作目录作为项目根目录
    return Path.cwd().resolve()


def _is_safe_command(command: str) -> tuple[bool, str]:
    """检查命令是否安全"""
    command = command.strip()

    if not command:
        return False, "❌ 错误: 命令不能为空"

    # 检查重定向操作符（在解析之前检查，因为可能无法解析）
    if command.strip().startswith(">") or command.strip().startswith(">>"):
        return False, f"❌ 错误: 禁止单独使用重定向操作符，可能被用于覆盖文件。"

    if COMMAND_WHITELIST:
        try:
            parts = shlex.split(command)
        except ValueError:
            return False, "❌ 错误: 无法解析命令（可能是语法错误）"
        if not parts:
            return False, "❌ 错误: 无法解析命令"

        cmd_name = parts[0].lower()
        if cmd_name not in COMMAND_WHITELIST:
            return (
                False,
                f"❌ 错误: 命令 '{cmd_name}' 不在白名单中。允许的命令: {', '.join(sorted(COMMAND_WHITELIST))}",
            )

    try:
        parts = shlex.split(command)
    except ValueError:
        return False, "❌ 错误: 无法解析命令（可能是语法错误）"
    if not parts:
        return False, "❌ 错误: 无法解析命令"

    cmd_name = parts[0].lower()

    if cmd_name in DANGEROUS_COMMANDS:
        return (
            False,
            f"❌ 错误: 禁止执行危险命令 '{cmd_name}'。该命令可能对系统造成损害。",
        )

    dangerous_patterns = ["&&", "||", ";", "$(", "`"]

    for pattern in dangerous_patterns:
        if pattern in command:
            return (
                False,
                f"❌ 错误: 命令中包含危险的操作符 '{pattern}'，可能被用于执行恶意操作或绕过安全检查。",
            )

    return True, ""


def _is_safe_working_directory(
    working_directory: Optional[str], project_root: Path
) -> Tuple[bool, Optional[Path], str]:
    """检查工作目录是否安全（不能跳转到项目外）"""
    if not working_directory:
        return True, project_root, ""

    try:
        work_dir = Path(working_directory)

        if not work_dir.is_absolute():
            resolved_path = (project_root / work_dir).resolve()
        else:
            resolved_path = work_dir.resolve()

        try:
            if not resolved_path.is_relative_to(project_root):
                return (
                    False,
                    None,
                    f"❌ 错误: 工作目录不能跳转到项目外。指定目录: {resolved_path}, 项目根目录: {project_root}",
                )
        except (ValueError, RuntimeError):
            return (
                False,
                None,
                f"❌ 错误: 无法解析工作目录路径。指定目录: {working_directory}",
            )

        if not resolved_path.exists():
            return False, None, f"❌ 错误: 工作目录不存在。路径: {resolved_path}"

        if not resolved_path.is_dir():
            return False, None, f"❌ 错误: 工作目录路径不是目录。路径: {resolved_path}"

        return True, resolved_path, ""

    except Exception as e:
        return False, None, f"❌ 错误: 检查工作目录时发生异常: {str(e)}"


def run_terminal_cmd(
    command: str,
    working_directory: Optional[str] = None,
    is_background: bool = False,
    timeout: int = 30,
) -> str:
    """执行系统命令并返回执行结果"""
    project_root = _get_project_root()

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

    work_dir = safe_work_dir if safe_work_dir else project_root

    if is_background:
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
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
                    "error": f"❌ 错误: 后台执行命令失败: {str(e)}",
                    "command": command,
                    "working_directory": str(work_dir),
                },
                ensure_ascii=False,
                indent=2,
            )

    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(work_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        execution_time = time.time() - start_time

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
                "error": f"❌ 错误: 命令执行超时（超过 {timeout} 秒）",
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
                "error": f"❌ 错误: 子进程执行失败: {str(e)}",
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
                "error": f"❌ 错误: 执行命令时发生未知异常: {str(e)}",
                "command": command,
                "working_directory": str(work_dir),
            },
            ensure_ascii=False,
            indent=2,
        )


class TestRunTerminalCmd(unittest.TestCase):
    """run_terminal_cmd 工具的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为测试根目录
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        # 切换到测试目录（确保路径解析正确）
        self.original_cwd = os.getcwd()
        os.chdir(self.test_root)

        # 创建测试文件
        (self.test_root / "test_file.txt").write_text("test content", encoding="utf-8")
        (self.test_root / "subdir").mkdir()
        (self.test_root / "subdir" / "nested_file.txt").write_text(
            "nested content", encoding="utf-8"
        )

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def parse_result(self, result_str: str) -> dict:
        """解析JSON格式的结果字符串"""
        return json.loads(result_str)

    # ==================== 命令执行测试 ====================

    def test_basic_command_execution(self):
        """测试：基本命令执行"""
        result_str = run_terminal_cmd("echo 'Hello World'")
        result = self.parse_result(result_str)

        # 验证返回结果结构
        self.assertIn("success", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("exit_code", result)
        self.assertIn("execution_time", result)
        self.assertIn("command", result)
        self.assertIn("working_directory", result)

        # 验证命令执行成功
        self.assertTrue(result["success"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("Hello World", result["stdout"])

    def test_command_with_output(self):
        """测试：命令输出捕获"""
        # 在Unix系统上使用echo，Windows上可能需要调整
        if os.name == "nt":
            command = "echo test output"
        else:
            command = "echo 'test output'"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        self.assertTrue(result["success"])
        self.assertIn("test output", result["stdout"].lower())

    def test_command_with_error(self):
        """测试：命令执行失败（非零退出码）"""
        # 使用一个会失败的命令
        if os.name == "nt":
            command = "exit /b 1"
        else:
            command = "false"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证命令执行失败
        self.assertFalse(result["success"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIsNotNone(result.get("error"))

    def test_command_stderr_capture(self):
        """测试：标准错误输出捕获"""
        # 使用一个会输出到stderr的命令
        if os.name == "nt":
            command = "echo error >&2"
        else:
            command = "echo error 1>&2"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证stderr被捕获（某些系统可能将stderr重定向到stdout）
        self.assertIsNotNone(result["stderr"])

    def test_execution_time_recorded(self):
        """测试：执行时间记录"""
        if os.name == "nt":
            command = "timeout /t 1 /nobreak >nul"
        else:
            command = "sleep 1"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证执行时间被记录
        self.assertIn("execution_time", result)
        self.assertIsInstance(result["execution_time"], (int, float))
        self.assertGreaterEqual(result["execution_time"], 0.9)  # 至少接近1秒

    def test_working_directory_relative(self):
        """测试：使用相对路径作为工作目录"""
        subdir = self.test_root / "subdir"

        if os.name == "nt":
            command = "cd"
        else:
            command = "pwd"

        result_str = run_terminal_cmd(command, working_directory="subdir")
        result = self.parse_result(result_str)

        # 验证命令在工作目录中执行
        self.assertTrue(result["success"])
        # 验证工作目录路径包含subdir
        self.assertIn("subdir", result["working_directory"])

    def test_working_directory_absolute(self):
        """测试：使用绝对路径作为工作目录"""
        subdir = self.test_root / "subdir"

        if os.name == "nt":
            command = "cd"
        else:
            command = "pwd"

        result_str = run_terminal_cmd(command, working_directory=str(subdir))
        result = self.parse_result(result_str)

        # 验证命令在工作目录中执行
        self.assertTrue(result["success"])
        self.assertIn("subdir", result["working_directory"])

    def test_working_directory_none(self):
        """测试：不指定工作目录（使用默认）"""
        if os.name == "nt":
            command = "cd"
        else:
            command = "pwd"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证使用默认工作目录
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["working_directory"])

    # ==================== 安全控制测试 ====================

    def test_dangerous_command_rm(self):
        """测试：禁止执行rm命令"""
        result_str = run_terminal_cmd("rm test_file.txt")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], -1)
        self.assertIn("错误", result["error"])
        self.assertIn("禁止执行危险命令", result["error"])
        self.assertIn("rm", result["error"])

        # 验证文件未被删除
        self.assertTrue((self.test_root / "test_file.txt").exists())

    def test_dangerous_command_mv(self):
        """测试：禁止执行mv命令"""
        result_str = run_terminal_cmd("mv test_file.txt renamed.txt")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("禁止执行危险命令", result["error"])
        self.assertIn("mv", result["error"])

        # 验证文件未被移动
        self.assertTrue((self.test_root / "test_file.txt").exists())

    def test_dangerous_command_dd(self):
        """测试：禁止执行dd命令"""
        result_str = run_terminal_cmd("dd if=/dev/zero of=test")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("禁止执行危险命令", result["error"])
        self.assertIn("dd", result["error"])

    def test_dangerous_command_shutdown(self):
        """测试：禁止执行shutdown命令"""
        result_str = run_terminal_cmd("shutdown -h now")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("禁止执行危险命令", result["error"])
        self.assertIn("shutdown", result["error"])

    def test_dangerous_command_sudo(self):
        """测试：禁止执行sudo命令"""
        result_str = run_terminal_cmd("sudo ls")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("禁止执行危险命令", result["error"])
        self.assertIn("sudo", result["error"])

    def test_dangerous_command_chmod(self):
        """测试：禁止执行chmod命令"""
        result_str = run_terminal_cmd("chmod 777 test_file.txt")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("禁止执行危险命令", result["error"])
        self.assertIn("chmod", result["error"])

    def test_command_chain_operator_and(self):
        """测试：禁止使用命令链操作符 &&"""
        result_str = run_terminal_cmd("echo test && echo test2")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])
        self.assertIn("危险的操作符", result["error"])
        self.assertIn("&&", result["error"])

    def test_command_chain_operator_or(self):
        """测试：禁止使用命令链操作符 ||"""
        result_str = run_terminal_cmd("echo test || echo test2")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("危险的操作符", result["error"])
        self.assertIn("||", result["error"])

    def test_command_chain_operator_semicolon(self):
        """测试：禁止使用命令链操作符 ;"""
        result_str = run_terminal_cmd("echo test; echo test2")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("危险的操作符", result["error"])
        self.assertIn(";", result["error"])

    def test_command_substitution_dollar(self):
        """测试：禁止使用命令替换 $()"""
        result_str = run_terminal_cmd("echo $(ls)")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("危险的操作符", result["error"])
        self.assertIn("$(", result["error"])

    def test_command_substitution_backtick(self):
        """测试：禁止使用命令替换 `"""
        result_str = run_terminal_cmd("echo `ls`")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("危险的操作符", result["error"])
        self.assertIn("`", result["error"])

    def test_redirect_operator_standalone(self):
        """测试：禁止单独使用重定向操作符 >"""
        result_str = run_terminal_cmd("> output.txt")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])
        # 注意：由于 > 在黑名单中，错误消息可能是"禁止执行危险命令"或"重定向操作符"
        self.assertTrue(
            "重定向操作符" in result["error"] or "禁止执行危险命令" in result["error"]
        )

    def test_redirect_operator_append_standalone(self):
        """测试：禁止单独使用重定向操作符 >>"""
        result_str = run_terminal_cmd(">> output.txt")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        # 注意：由于 >> 在黑名单中，可能先匹配黑名单检查，所以错误消息可能是"禁止执行危险命令"或"重定向操作符"
        # 两种错误消息都是可以接受的，都表示命令被正确拒绝
        self.assertTrue(
            "重定向操作符" in result["error"]
            or "禁止执行危险命令" in result["error"]
            or ">>" in result["error"]
        )

    def test_working_directory_parent(self):
        """测试：不允许工作目录跳转到项目外"""
        parent_dir = self.test_root.parent

        result_str = run_terminal_cmd("pwd", working_directory=str(parent_dir))
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])
        self.assertIn("不能跳转到项目外", result["error"])

    def test_working_directory_absolute_parent(self):
        """测试：不允许使用绝对路径跳转到项目外"""
        # 尝试使用绝对路径跳转到父目录
        parent_dir = self.test_root.parent

        result_str = run_terminal_cmd("pwd", working_directory=str(parent_dir))
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("不能跳转到项目外", result["error"])

    def test_working_directory_relative_parent(self):
        """测试：不允许使用相对路径跳转到项目外"""
        # 尝试使用 .. 跳转到父目录
        result_str = run_terminal_cmd("pwd", working_directory="../")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("不能跳转到项目外", result["error"])

    def test_working_directory_nonexistent(self):
        """测试：工作目录不存在时的错误处理"""
        result_str = run_terminal_cmd("pwd", working_directory="nonexistent_dir")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])
        self.assertIn("工作目录不存在", result["error"])

    def test_working_directory_not_directory(self):
        """测试：工作目录路径不是目录时的错误处理"""
        test_file = self.test_root / "test_file.txt"

        result_str = run_terminal_cmd("pwd", working_directory=str(test_file))
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])
        self.assertIn("不是目录", result["error"])

    def test_empty_command(self):
        """测试：空命令的错误处理"""
        result_str = run_terminal_cmd("")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])
        self.assertIn("命令不能为空", result["error"])

    def test_whitespace_only_command(self):
        """测试：只有空白字符的命令"""
        result_str = run_terminal_cmd("   ")
        result = self.parse_result(result_str)

        # 验证命令被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])

    # ==================== 超时处理测试 ====================

    def test_timeout_normal_execution(self):
        """测试：正常执行不超时"""
        if os.name == "nt":
            command = "echo test"
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command, timeout=10)
        result = self.parse_result(result_str)

        # 验证命令正常执行
        self.assertTrue(result["success"])
        # 验证没有超时错误
        error_msg = result.get("error") or ""
        self.assertNotIn("超时", error_msg)

    def test_timeout_expired(self):
        """测试：命令执行超时"""
        if os.name == "nt":
            command = "timeout /t 5 /nobreak >nul"
            timeout = 1
        else:
            command = "sleep 5"
            timeout = 1

        result_str = run_terminal_cmd(command, timeout=timeout)
        result = self.parse_result(result_str)

        # 验证命令超时
        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], -1)
        self.assertIn("超时", result["error"])
        self.assertIn(str(timeout), result["error"])

    def test_timeout_custom_value(self):
        """测试：自定义超时时间"""
        if os.name == "nt":
            command = "timeout /t 2 /nobreak >nul"
            timeout = 1
        else:
            command = "sleep 2"
            timeout = 1

        result_str = run_terminal_cmd(command, timeout=timeout)
        result = self.parse_result(result_str)

        # 验证命令超时
        self.assertFalse(result["success"])
        self.assertIn("超时", result["error"])

    def test_timeout_zero(self):
        """测试：超时时间为0（应该立即超时或正常执行）"""
        if os.name == "nt":
            command = "echo test"
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command, timeout=0)
        result = self.parse_result(result_str)

        # 验证结果（可能是超时或成功，取决于实现）
        self.assertIsNotNone(result)
        self.assertIn("success", result)

    def test_timeout_large_value(self):
        """测试：超时时间很大"""
        if os.name == "nt":
            command = "echo test"
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command, timeout=3600)
        result = self.parse_result(result_str)

        # 验证命令正常执行
        self.assertTrue(result["success"])

    def test_timeout_execution_time_recorded(self):
        """测试：超时时执行时间被记录"""
        if os.name == "nt":
            command = "timeout /t 3 /nobreak >nul"
            timeout = 1
        else:
            command = "sleep 3"
            timeout = 1

        result_str = run_terminal_cmd(command, timeout=timeout)
        result = self.parse_result(result_str)

        # 验证执行时间被记录
        self.assertIn("execution_time", result)
        self.assertGreaterEqual(result["execution_time"], timeout - 0.1)  # 接近超时时间
        self.assertLess(result["execution_time"], timeout + 0.5)  # 不超过超时时间太多

    # ==================== 后台执行测试 ====================

    def test_background_execution_flag(self):
        """测试：后台执行标志"""
        if os.name == "nt":
            command = "echo test"
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command, is_background=True)
        result = self.parse_result(result_str)

        # 验证后台执行标志
        self.assertTrue(result["success"])
        self.assertIn("background", result)
        self.assertTrue(result["background"])
        self.assertIn("pid", result)
        self.assertIsInstance(result["pid"], int)
        self.assertGreater(result["pid"], 0)

    def test_background_execution_immediate_return(self):
        """测试：后台执行立即返回"""
        if os.name == "nt":
            command = "timeout /t 10 /nobreak >nul"
        else:
            command = "sleep 10"

        start_time = time.time()
        result_str = run_terminal_cmd(command, is_background=True)
        execution_time = time.time() - start_time

        result = self.parse_result(result_str)

        # 验证立即返回（不应该等待命令完成）
        self.assertTrue(result["success"])
        self.assertLess(execution_time, 2.0)  # 应该在2秒内返回
        self.assertIn("pid", result)

    def test_background_execution_no_output(self):
        """测试：后台执行不捕获输出"""
        if os.name == "nt":
            command = "echo test output"
        else:
            command = "echo 'test output'"

        result_str = run_terminal_cmd(command, is_background=True)
        result = self.parse_result(result_str)

        # 验证输出为空（后台执行不捕获输出）
        self.assertTrue(result["success"])
        self.assertEqual(result["stdout"], "")
        self.assertEqual(result["stderr"], "")
        self.assertIsNone(result.get("exit_code"))

    def test_background_execution_pid_valid(self):
        """测试：后台执行的PID有效"""
        if os.name == "nt":
            command = "echo test"
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command, is_background=True)
        result = self.parse_result(result_str)

        # 验证PID有效
        self.assertIn("pid", result)
        pid = result["pid"]
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

        # 验证进程存在（在某些系统上可能已经结束）
        # 注意：进程可能已经完成，所以这个检查可能失败
        # 这里只验证PID格式正确

    def test_background_execution_message(self):
        """测试：后台执行返回的消息"""
        if os.name == "nt":
            command = "echo test"
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command, is_background=True)
        result = self.parse_result(result_str)

        # 验证消息存在
        self.assertIn("message", result)
        self.assertIn("后台启动", result["message"])
        self.assertIn("PID", result["message"])

    def test_background_execution_with_working_directory(self):
        """测试：后台执行使用工作目录"""
        subdir = self.test_root / "subdir"

        if os.name == "nt":
            command = "cd"
        else:
            command = "pwd"

        result_str = run_terminal_cmd(
            command, working_directory="subdir", is_background=True
        )
        result = self.parse_result(result_str)

        # 验证后台执行成功
        self.assertTrue(result["success"])
        self.assertIn("subdir", result["working_directory"])

    # ==================== 边界情况和异常场景测试 ====================

    def test_nonexistent_command(self):
        """测试：不存在的命令"""
        result_str = run_terminal_cmd("nonexistent_command_xyz123")
        result = self.parse_result(result_str)

        # 验证命令执行失败
        self.assertFalse(result["success"])
        self.assertNotEqual(result["exit_code"], 0)

    def test_invalid_command_syntax(self):
        """测试：无效的命令语法"""
        result_str = run_terminal_cmd("echo 'unclosed quote")
        result = self.parse_result(result_str)

        # 验证命令被拒绝（因为无法解析）
        self.assertIsNotNone(result)
        self.assertIn("success", result)
        # 由于语法错误，命令应该被拒绝
        self.assertFalse(result["success"])
        self.assertIn("错误", result["error"])

    def test_command_with_special_characters(self):
        """测试：命令中包含特殊字符（但不在黑名单中）"""
        if os.name == "nt":
            command = 'echo "test with spaces"'
        else:
            command = "echo 'test with spaces'"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证命令正常执行
        self.assertTrue(result["success"])
        self.assertIn("test", result["stdout"].lower())

    def test_command_with_quotes(self):
        """测试：命令中包含引号"""
        if os.name == "nt":
            command = 'echo "test"'
        else:
            command = "echo 'test'"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证命令正常执行
        self.assertTrue(result["success"])

    def test_command_with_spaces(self):
        """测试：命令中包含空格"""
        if os.name == "nt":
            command = "echo test with spaces"
        else:
            command = "echo 'test with spaces'"

        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证命令正常执行
        self.assertTrue(result["success"])

    def test_working_directory_subdirectory(self):
        """测试：工作目录为子目录"""
        subdir = self.test_root / "subdir"

        if os.name == "nt":
            command = "dir"
        else:
            command = "ls"

        result_str = run_terminal_cmd(command, working_directory="subdir")
        result = self.parse_result(result_str)

        # 验证命令在工作目录中执行
        self.assertTrue(result["success"])
        self.assertIn("subdir", result["working_directory"])

    def test_working_directory_nested_subdirectory(self):
        """测试：工作目录为嵌套子目录"""
        nested_dir = self.test_root / "subdir" / "nested"
        nested_dir.mkdir(exist_ok=True)

        if os.name == "nt":
            command = "cd"
        else:
            command = "pwd"

        result_str = run_terminal_cmd(command, working_directory="subdir/nested")
        result = self.parse_result(result_str)

        # 验证命令在工作目录中执行
        self.assertTrue(result["success"])
        self.assertIn("nested", result["working_directory"])

    def test_result_json_format(self):
        """测试：返回结果为有效的JSON格式"""
        result_str = run_terminal_cmd("echo test")

        # 验证可以解析为JSON
        try:
            result = json.loads(result_str)
            self.assertIsInstance(result, dict)
        except json.JSONDecodeError:
            self.fail("返回结果不是有效的JSON格式")

    def test_result_contains_all_fields(self):
        """测试：返回结果包含所有必需字段"""
        result_str = run_terminal_cmd("echo test")
        result = self.parse_result(result_str)

        # 验证所有必需字段存在
        required_fields = [
            "success",
            "stdout",
            "stderr",
            "exit_code",
            "execution_time",
            "command",
            "working_directory",
        ]
        for field in required_fields:
            self.assertIn(field, result, f"缺少必需字段: {field}")

    def test_command_preserved_in_result(self):
        """测试：命令在结果中被保留"""
        command = "echo 'test command'"
        result_str = run_terminal_cmd(command)
        result = self.parse_result(result_str)

        # 验证命令被保留
        self.assertEqual(result["command"], command)

    def test_working_directory_preserved_in_result(self):
        """测试：工作目录在结果中被保留"""
        working_dir = "subdir"
        result_str = run_terminal_cmd("pwd", working_directory=working_dir)
        result = self.parse_result(result_str)

        # 验证工作目录被保留
        self.assertIn(working_dir, result["working_directory"])

    def test_multiple_dangerous_commands(self):
        """测试：测试多个危险命令"""
        dangerous_commands = ["rm", "mv", "dd", "shutdown", "sudo", "chmod"]

        for cmd in dangerous_commands:
            if os.name == "nt" and cmd in ["rm", "mv", "dd", "shutdown"]:
                # Windows上某些命令可能不存在，跳过
                continue

            result_str = run_terminal_cmd(f"{cmd} test")
            result = self.parse_result(result_str)

            # 验证命令被拒绝
            self.assertFalse(result["success"], f"危险命令 {cmd} 应该被拒绝")
            self.assertIn("禁止执行危险命令", result["error"])

    def test_safe_command_allowed(self):
        """测试：安全命令被允许执行"""
        safe_commands = ["echo", "pwd", "ls", "cat"]

        for cmd in safe_commands:
            if os.name == "nt" and cmd in ["ls", "cat", "pwd"]:
                # Windows上使用不同的命令
                if cmd == "ls":
                    cmd = "dir"
                elif cmd == "cat":
                    cmd = "type"
                elif cmd == "pwd":
                    cmd = "cd"

            result_str = run_terminal_cmd(
                f"{cmd} test" if cmd != "pwd" and cmd != "cd" else cmd
            )
            result = self.parse_result(result_str)

            # 验证命令被允许（可能执行成功或失败，但不应该因为安全原因被拒绝）
            # 注意：某些命令可能在系统上不存在，所以可能失败，但不应该是因为安全原因
            if not result["success"]:
                # 如果失败，不应该是因为安全原因
                self.assertNotIn(
                    "禁止执行危险命令",
                    result.get("error", ""),
                    f"安全命令 {cmd} 不应该被安全机制拒绝",
                )

    def test_working_directory_resolution(self):
        """测试：工作目录路径解析"""
        # 创建测试目录
        test_subdir = self.test_root / "test_subdir"
        test_subdir.mkdir()

        # 使用相对路径
        result_str = run_terminal_cmd("pwd", working_directory="test_subdir")
        result = self.parse_result(result_str)

        # 验证路径被正确解析
        self.assertTrue(result["success"])
        self.assertIn("test_subdir", result["working_directory"])


if __name__ == "__main__":
    unittest.main()
