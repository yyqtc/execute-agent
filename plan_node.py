from custom_type import PlanExecute
from pathlib import Path
from typing import List, Union

import re
import os
import json
import logging

logger = logging.getLogger(__name__)


def todo_write(merge: bool, todos: list) -> str:
    """创建和管理任务列表

    Args:
        merge: 是否合并任务列表。当 merge=True 时，将传入的 todos 列表与已存在的任务列表合并（去重，基于任务描述）。
               当 merge=False 时，直接覆盖原有任务列表。
        todos: 任务列表，每个任务为字典，包含字段：
               - desc: 任务描述（str，必需）
               - status: 任务状态（str，可选，默认为 "pending"）

    Returns:
        操作结果消息字符串。成功时返回 "Tasks saved successfully."，失败时返回错误消息。

    功能说明:
        - 支持任务的创建与管理
        - 当 merge=True 时，将传入的 todos 列表与已存在的任务列表合并（去重，基于任务描述）
        - 当 merge=False 时，直接覆盖原有任务列表
        - 任务数据结构为字典列表，每个任务包含字段：desc（任务描述，str）、status（状态，str，默认"pending"）
        - 所有任务持久化存储在 data/todos.json 文件中（需确保目录存在）
        - 若 todos 中的任务无 status 字段，自动补全为 "pending"
        - 成功写入后返回 "Tasks saved successfully."
        - 首次运行时若文件不存在，应初始化为空列表
        - 确保路径安全检查，不允许对父目录进行写入操作
    """
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
            return f"错误: 权限不足，无法创建目录。路径: {todos_file.parent}, 错误: {str(e)}"
        except Exception as e:
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
                # JSON 格式错误，使用空列表
                existing_todos = []
            except IOError as e:
                return f"错误: 读取文件失败。路径: {todos_file}, 错误: {str(e)}"
            except Exception as e:
                return f"错误: 读取任务列表时发生未知错误。路径: {todos_file}, 错误: {str(e)}"

        # 验证输入参数
        if not isinstance(todos, list):
            return f"错误: todos 参数必须是列表类型，当前类型: {type(todos).__name__}"

        # 处理新任务列表：确保每个任务都有 status 字段
        processed_todos = []
        for todo in todos:
            if not isinstance(todo, dict):
                return f"错误: 任务必须是字典类型，当前类型: {type(todo).__name__}"

            # 检查必需字段 desc
            if "desc" not in todo:
                return f"错误: 任务缺少必需字段 'desc'。任务: {todo}"

            # 确保 desc 是字符串类型
            if not isinstance(todo.get("desc"), str):
                return f"错误: 任务 'desc' 字段必须是字符串类型。任务: {todo}"

            # 创建处理后的任务字典
            processed_todo = {
                "desc": str(todo["desc"]),
                "status": str(todo.get("status", "pending")),
            }

            processed_todos.append(processed_todo)

        # 根据 merge 参数决定是合并还是覆盖
        if merge:
            # 合并模式
            todos_arr = []

            # 先添加现有任务
            for todo in existing_todos:
                if isinstance(todo, dict) and "desc" in todo:
                    desc = str(todo["desc"])
                    todos_arr.append(
                        {
                            "desc": desc,
                            "status": str(todo.get("status", "pending")),
                        }
                    )

            index = 0
            for todo in processed_todos:
                desc = todo["desc"]
                if index < len(todos_arr) and desc == todos_arr[index]["desc"]:
                    index += 1
                    continue
                elif index < len(todos_arr) and desc != existing_todos[index]["desc"]:
                    todos_arr.insert(index, todo)
                    index += 1
                else:
                    todos_arr.append(todo)

            # 转换为列表
            final_todos = todos_arr
        else:
            # 覆盖模式：直接使用新任务列表
            final_todos = processed_todos

        # 检查写入权限
        if todos_file.exists() and not os.access(todos_file, os.W_OK):
            return f"错误: 没有写入权限。路径: {todos_file}"

        # 写入文件（使用 UTF-8 编码）
        try:
            with open(todos_file, "w", encoding="utf-8") as f:
                json.dump(final_todos, f, ensure_ascii=False, indent=2)
            return "Tasks saved successfully."
        except UnicodeEncodeError as e:
            return f"错误: 内容编码错误，无法使用 UTF-8 编码。路径: {todos_file}, 错误: {str(e)}"
        except IOError as e:
            return f"错误: 写入文件失败。路径: {todos_file}, 错误: {str(e)}"
        except OSError as e:
            return (
                f"错误: 操作系统错误，无法写入文件。路径: {todos_file}, 错误: {str(e)}"
            )

    except PermissionError as e:
        return f"错误: 权限不足，无法访问路径。错误: {str(e)}"
    except Exception as e:
        return f"错误: 保存任务列表时发生未知错误。错误: {str(e)}"


def parse_parallel_tasks(steps: List[str]) -> List[Union[str, List[str]]]:
    """
    将带 [PARALLEL-X] 标记的任务列表转换为可执行的结构
    
    输入：
    [
        "[PARALLEL-1] 任务1",
        "[PARALLEL-2] 任务A",
        "[PARALLEL-2] 任务B",
        "[PARALLEL-3] 任务C",
        "[PARALLEL-4] 任务2"
    ]
    
    输出：
    [
        ["任务1"],
        ["任务A", "任务B"],  # 并行组1
        ["任务C"], # 并行组2
        ["任务2"]
    ]
    """
    import re
    
    result = []
    parallel_groups = {}
    
    for step in steps:
        match = re.match(r'\[PARALLEL-(\d+)\]\s*(.+)', step)
        
        if match:
            group_id = match.group(1)
            task_desc = match.group(2)
            
            if group_id not in parallel_groups:
                parallel_groups[group_id] = []
            parallel_groups[group_id].append(task_desc)
        else:
            # 先清空之前的并行组
            for gid in sorted(parallel_groups.keys()):
                tasks = parallel_groups[gid]
                if len(tasks) == 1:
                    result.append([tasks[0]])
                else:
                    result.append(tasks)
            parallel_groups.clear()
            
            # 添加当前任务
            result.append([step])
    
    # 处理最后的并行组
    for gid in sorted(parallel_groups.keys()):
        tasks = parallel_groups[gid]
        result.append(tasks)
    
    return result


async def plan_node(state: PlanExecute) -> PlanExecute:
    """
    计划节点
    """
    # 延迟导入避免循环导入，并确保在函数执行时获取最新的 agent 值
    from agent_instance import plan_agent as agent
    
    if agent is None:
        logger.error("plan_agent 未初始化")
        return {"response": "计划生成失败，plan_agent 未初始化"}
    
    result = await agent.ainvoke({"input": state["input"]})

    result = result.steps
    if result is None or len(result) == 0:
        return {"response": "计划生成失败，返回为空"}
    else:
        plan_table = [{"desc": re.match(r'\[PARALLEL-(\d+)\]\s*(.+)', step).group(2), "status": "pending"} for step in result]
        todo_write(False, plan_table)

        result = parse_parallel_tasks(result)
        return {
            "plan": result
        }
