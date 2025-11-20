from custom_type import PlanExecute
from pathlib import Path
from load_config import config

import os
import json
import logging

logger = logging.getLogger(__name__)


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
        return f"错误: 权限不足，无法访问路径。错误: {str(e)}"
    except Exception as e:
        return f"错误: 保存任务列表时发生未知错误。错误: {str(e)}"


async def execute_node(state: PlanExecute) -> PlanExecute:
    """
    执行节点
    """
    # 延迟导入避免循环导入，并确保在函数执行时获取最新的 agent 值
    from agent_instance import normal_execute_agent, summary_agent
    
    if not state["plan"] or not len(state["plan"]):
        return {"response": "没有计划，无需执行"}

    refresh_todo_list(state["index"], "processing")
    task = state["plan"].pop(0)

    past_achievement = state.get("past_achievement", [])
    if past_achievement and len(past_achievement) > 0:
        past_achievement_content = "\n\n".join(
            [
                f"步骤：{step}\n\n响应：\n{response}"
                for step, response in past_achievement
            ]
        )
        if len(past_achievement_content) > config["SUMMARY_THRESHOLD"]:
            if summary_agent is None:
                logger.error("summary_agent 为 None，无法执行总结操作")
                return {"response": "model 未初始化，无法执行总结操作"}
            past_achievement_content_wrapper = await summary_agent.ainvoke(
                {"input": past_achievement_content}
            )
            past_achievement_content = past_achievement_content_wrapper.content
            past_achievement = [("过往任务总结", past_achievement_content)]
    else:
        past_achievement_content = ""

    if past_achievement_content and len(past_achievement_content) > 0:
        formatted_task = f"""
        这是我们已经执行过的步骤和取得的成果：
        {past_achievement_content}

        完成这个任务：{task}。不要做无关的事情。
        """
    else:
        formatted_task = f"""
        完成这个任务：{task}。不要做无关的事情。
        """

    if normal_execute_agent is None:
        logger.error("normal_execute_agent 未初始化")
        refresh_todo_list(state["index"], "fail", "执行智能体初始化失败")
        return {"response": "执行智能体初始化失败"}

    result = await normal_execute_agent.ainvoke(
        {"messages": [("user", formatted_task)]},
        {"recursion_limit": config["RECURSION_LIMIT"]},
    )

    try:
        messages = result.get("messages", None)
        if messages is None:
            refresh_todo_list(state["index"], "fail", "执行任务完成，返回为空")
            return {"response": "执行任务完成，返回为空"}

        response = messages[-1].content
        refresh_todo_list(state["index"], "done", response)

        return {
            "past_achievement": past_achievement + [(task, response)],
            "past_steps": [task],
            "index": state["index"] + 1,
        }
    except Exception as e:
        logging.error(f"执行任务失败: {str(e)}")
        refresh_todo_list(state["index"], "fail", f"执行任务失败: {str(e)}")
        return {"response": f"执行任务失败: {str(e)}"}
