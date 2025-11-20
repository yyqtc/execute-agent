from custom_type import PlanExecute, Plan, Response
from pathlib import Path
from load_config import config

import os
import json
import logging

logger = logging.getLogger(__name__)

def todo_write(merge: bool, todos: list, start_index: int) -> str:
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
            # 合并模式：将 processed_todos 合并到 existing_todos 中
            # 从 start_index 开始插入新任务，保持顺序并去重

            # 转换为列表
            final_todos = existing_todos[:start_index] + processed_todos
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


async def replan_node(state: PlanExecute) -> PlanExecute:
    """
    计划节点
    """
    # 延迟导入避免循环导入，并确保在函数执行时获取最新的 agent 值
    from agent_instance import replan_agent as agent
    from agent_instance import summary_agent

    plan_list = "\n".join([f"- {step}" for step in state["plan"]])

    past_achievement = state.get("past_achievement", [])
    past_achievement_content = "\n\n".join(
        [f"步骤：{step}\n\n响应：\n{response}" for step, response in past_achievement]
    )
    if len(past_achievement_content) > config["SUMMARY_THRESHOLD"]:
        if summary_agent is None:
            logger.error("summary_agent为None，无法执行总结操作")
            raise ValueError("model未初始化，无法执行总结操作")
        past_achievement_content_wrapper = await summary_agent.ainvoke(
            {"input": past_achievement_content}
        )
        past_achievement_content = past_achievement_content_wrapper.content
        past_achievement = [("过往任务总结", past_achievement_content)]

    past_steps = state.get("past_steps", [])
    past_steps_content = "\n".join([f"- {step}" for step in past_steps])

    user_prompt = f"""
    我们的客户的需求是（注意！你不能做任何偏离客户需求的指示！）：
    {state["input"]}
    
    我们最近一次计划是：
    {plan_list}
    
    我们执行过的步骤以及取得的成果是：
    {past_achievement_content}

    我们已经执行过的步骤是：
    {past_steps_content}
    
    根据以上信息更新我们的计划。如果你认为不需要执行更多步骤，你可以直接输出对用户问题的最终答案。否则你需要在计划中补充更多步骤。
    """

    if agent is None:
        logger.error("agent未初始化，无法执行计划更新")
        return {"response": "计划更新失败，agent未初始化"}

    result = await agent.ainvoke({"input": user_prompt})
    result = result.action
    if result is None:
        return {"response": "计划更新失败，返回为空"}

    elif isinstance(result, Response):
        return {"response": result.response}
    elif isinstance(result, Plan):
        plan_table = [{"desc": step, "status": "pending"} for step in result.steps]
        todo_write(True, plan_table, state["index"])
        return {"plan": result.steps, "past_achievement": past_achievement}
