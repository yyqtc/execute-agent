from custom_type import PlanExecute
from pathlib import Path
from load_config import config

import os
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


async def gather_project_structure(dir_path: str, layer: int = 5):
    """
    返回当前文件夹下5层内的所有文件
    """
    if layer == 5:
        return []
    
    # 定义要忽略的目录和文件（减少 Token 消耗）
    IGNORE_DIRS = {
        '.git', '__pycache__', 'node_modules', 'venv', '.idea', '.vscode', 
        'dist', 'build', 'coverage', '.pytest_cache'
    }

    IGNORE_FILES = {
        '.DS_Store', 'package-lock.json', 'yarn.lock', 'poetry.lock'
    }

    result = []
    async_tasks = []
    file_and_dir_list = os.listdir(dir_path)
    for file_or_dir in file_and_dir_list:
        if os.path.isdir(os.path.join(dir_path, file_or_dir)) and file_or_dir not in IGNORE_DIRS:
            async_tasks.append(gather_project_structure(os.path.join(dir_path, file_or_dir), layer + 1))
        elif file_or_dir not in IGNORE_FILES:
            result.append(os.path.join(dir_path, file_or_dir))

    if len(async_tasks) > 0:
        results = await asyncio.gather(*async_tasks)
        for result_item in results:
            result.extend(result_item)
    
    if layer == 0:
        rel_paths = []
        for p in result:
            try:
                rel_paths.append(os.path.relpath(p, dir_path))
            except ValueError:
                rel_paths.append(p)
        
        rel_paths.sort()
        tree_structure = {}
        for path in rel_paths:
            parts = path.split(os.sep)
            current = tree_structure
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]

        # 3. 递归生成 Tree 字符串
        def _build_tree_string(node, prefix=""):
            lines = []
            keys = sorted(node.keys())
            for i, key in enumerate(keys):
                is_last = (i == len(keys) - 1)
                connector = "└── " if is_last else "├── "
                
                # 判断是否是目录（如果有子节点则是目录）
                is_dir = len(node[key]) > 0
                display_name = f"{key}/" if is_dir else key
                
                lines.append(f"{prefix}{connector}{display_name}")
                
                if is_dir:
                    extension = "    " if is_last else "│   "
                    lines.extend(_build_tree_string(node[key], prefix + extension))
            return lines

        return ("\n".join(_build_tree_string(tree_structure)), "project_structure")

    else:
        return result


async def gather_development_log():
    """
    如果开发日志存在，则读取开发日志
    """
    working_dir = os.getcwd()
    development_log_file = os.path.join(working_dir, "development_log.md")
    
    def _read_log_sync(file_path: str) -> str:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return "当前文件夹下没有开发日志"

    def _write_log_sync(file_path: str, log_content: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log_content)

    def _truncate_log_content(log_content: str) -> str:
        return log_content[-1 * config["SUMMARY_MAX_LENGTH"]:]

    loop = asyncio.get_running_loop()
    log_content = await loop.run_in_executor(None, _read_log_sync, development_log_file)

    if len(log_content) < config["SUMMARY_THRESHOLD"]:
        return (log_content, "development_log")
    else:
        from agent_instance import summary_agent
        if summary_agent is None:
            return (_truncate_log_content(log_content), "development_log")

        summary_result_wrapper = await summary_agent.ainvoke(
            {"input": log_content}
        )
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _write_log_sync, development_log_file, summary_result_wrapper.content)
        return (summary_result_wrapper.content, "development_log")


async def gather_dependencies():
    """
    收集可能的项目依赖
    """
    working_dir = os.getcwd()
    
    # 定义我们要查找的依赖文件清单
    # 优先级高的在前
    possible_dependency_files = [
        "requirements.txt",
        "package.json",
        "pyproject.toml",
        "Pipfile",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle"
    ]

    found_any = False
    def _find_dependency_sync():
        nonlocal found_any
        dependency_list = []
        for dependency_file in possible_dependency_files:
            dependency_file_path = os.path.join(working_dir, dependency_file)
            if os.path.exists(dependency_file_path):
                try:
                    with open(dependency_file_path, "r", encoding="utf-8") as f:
                        dependency_list.append(f.read())
                    found_any = True
                except Exception as e:
                    logging.error(f"读取依赖文件失败: {dependency_file_path}, 错误: {str(e)}")
                    continue

        return dependency_list

    loop = asyncio.get_running_loop()
    output = await loop.run_in_executor(None, _find_dependency_sync)

    if not found_any:
        return ("没有找到项目依赖", "dependencies")
    else:
        return ("\n".join(output), "dependencies")


def refresh_todo_list(index: int, status: str, response: str = ""):
    try:
        # 获取项目根目录
        project_root = Path(__file__).parent.resolve()

        # 构建文件路径
        todos_file = project_root / "data" / "todos.json"

        # 安全检查：确保路径在项目根目录内
        try:
            if not todos_file.resolve().is_relative_to(project_root):
                return f"错误: 不允许写入父目录。目标路径: {todos_file.resolve()}, 项目根目录: {project_root}"
        except (ValueError, RuntimeError):
            return f"错误: 路径解析失败，可能不安全。目标路径: {todos_file}"

        # 确保 data 目录存在
        try:
            todos_file.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            logging.error(
                f"权限不足，无法创建目录。路径: {todos_file.parent}, 错误: {str(e)}"
            )
            return f"错误: 权限不足，无法创建目录。路径: {todos_file.parent}, 错误: {str(e)}"
        except Exception as e:
            logging.error(f"创建目录失败。路径: {todos_file.parent}, 错误: {str(e)}")
            return f"错误: 创建目录失败。路径: {todos_file.parent}, 错误: {str(e)}"

        # 读取现有任务列表（如果文件存在）
        existing_todos = []
        if todos_file.exists():
            try:
                # 检查读取权限
                if not os.access(todos_file, os.R_OK):
                    return f"错误: 没有读取权限。路径: {todos_file}"

                # 读取文件内容
                with open(todos_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        existing_todos = json.loads(content)
                        # 验证数据格式
                        if not isinstance(existing_todos, list):
                            existing_todos = []
            except json.JSONDecodeError as e:
                logging.error(
                    f"JSON 格式错误，使用空列表。路径: {todos_file}, 错误: {str(e)}"
                )
                existing_todos = []
            except IOError as e:
                logging.error(f"读取文件失败。路径: {todos_file}, 错误: {str(e)}")
                return f"错误: 读取文件失败。路径: {todos_file}, 错误: {str(e)}"
            except Exception as e:
                logging.error(
                    f"读取任务列表时发生未知错误。路径: {todos_file}, 错误: {str(e)}"
                )
                return f"错误: 读取任务列表时发生未知错误。路径: {todos_file}, 错误: {str(e)}"

        if len(existing_todos) > 0 and index < len(existing_todos):
            existing_todos[index]["status"] = status
            if response and len(response) > 0:
                existing_todos[index]["response"] = response

            with open(todos_file, "w", encoding="utf-8") as f:
                json.dump(existing_todos, f, ensure_ascii=False, indent=2)

            return "任务列表更新成功"
        else:
            return "任务列表为空，无需更新"

    except PermissionError as e:
        logging.error(f"权限不足，无法访问路径。错误: {str(e)}")
        return f"错误: 权限不足，无法访问路径。错误: {str(e)}"
    except Exception as e:
        logging.error(f"保存任务列表时发生未知错误。错误: {str(e)}")
        return f"错误: 保存任务列表时发生未知错误。错误: {str(e)}"


async def execute_node(state: PlanExecute) -> PlanExecute:
    """
    执行节点
    """
    # 延迟导入避免循环导入，并确保在函数执行时获取最新的 agent 值
    # from agent_instance import recommend_agent, recommend_check_agent
    from agent_instance import code_agent
    
    if not state["plan"] or not len(state["plan"]):
        return {"response": "没有计划，无需执行"}

    refresh_todo_list(state["index"], "processing")
    task = state["plan"].pop(0)

    async_tasks = [
        gather_project_structure(os.getcwd(), 0),
        gather_development_log(),
        gather_dependencies(),
    ]

    contexts = await asyncio.gather(*async_tasks)

    project_structure = ""
    development_log = ""
    dependencies = ""
    for context in contexts:
        if context[1] == "project_structure":
            project_structure = context[0]
        elif context[1] == "development_log":
            development_log = context[0]
        elif context[1] == "dependencies":
            dependencies = context[0]

    detailed_task = f"""
    项目结构：
    {project_structure}
    
    开发日志：
    {development_log}

    项目依赖：
    {dependencies}

    完成这个任务：{task}。不要做无关的事情。
    """

    logger.info(f"执行任务: {detailed_task}")

    result = await code_agent.ainvoke(
        {"messages": [("user", detailed_task)]},
        {"recursion_limit": config["RECURSION_LIMIT"]},
    )

    try:
        messages = result.get("messages", None)
        if messages is None:
            refresh_todo_list(state["index"], "fail", "执行任务完成，返回为空")
            return {"response": "执行任务完成，返回为空"}

        response = messages[-1].content
        refresh_todo_list(state["index"], "done", response)

        past_achievement = state.get("past_achievement", [])
        return {
            "past_achievement": past_achievement + [(task, response)],
            "past_steps": [task],
            "index": state["index"] + 1,
        }

    except Exception as e:
        logging.error(f"执行任务失败: {str(e)}")
        refresh_todo_list(state["index"], "fail", f"执行任务失败: {str(e)}")
        return {"response": f"执行任务失败: {str(e)}"}
