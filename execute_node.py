from utils.coder_context import gather_project_structure, gather_development_log, gather_dependencies
from tools import set_task_context, clear_task_context, get_file_manager
from custom_type import PlanExecute
from pathlib import Path
from load_config import config

import os
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

async def refresh_todo_list(index: int, status: str, response: str = "", task_id: str = "", enable_lock: bool = False):
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

        def write_json_file(todo_file, todo):
            with open(todo_file, "w", encoding="utf-8") as f:
                json.dump(todo, f, ensure_ascii=False, indent=2)

            with open(todos_file, "w", encoding="utf-8") as f:
                json.dump(existing_todos, f, ensure_ascii=False, indent=2)

        if len(existing_todos) > 0 and index < len(existing_todos):
            existing_todos[index]["status"] = status
            if response and len(response) > 0:
                existing_todos[index]["response"] = response
            if enable_lock:
                manager = get_file_manager()
                async with manager.write_lock(todos_file, task_id, timeout=10):
                    await asyncio.to_thread(write_json_file, todos_file, existing_todos)
                    
            else:
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


async def normal_execute_node(state: PlanExecute, enable_lock: bool = False) -> PlanExecute:
    """
    执行节点
    """
    # 延迟导入避免循环导入，并确保在函数执行时获取最新的 agent 值
    from agent_instance import normal_execute_agent, summary_agent
    
    if not state["plan"] or not len(state["plan"]):
        return {
            "response": "没有计划，无需执行",
            "past_steps": []
        }

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
                return {
                    "response": "model 未初始化，无法执行总结操作",
                    "past_steps": [task]
                }
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

    if enable_lock:
        manager = get_file_manager()
        set_task_context(f"normal_execute_{state['index']}", manager)

    try:
        await refresh_todo_list(state["index"], "processing", task_id=f"normal_execute_{state['index']}", enable_lock=enable_lock)
        if normal_execute_agent is None:
            logger.error("normal_execute_agent 未初始化")
            await refresh_todo_list(state["index"], "fail", "执行智能体初始化失败", task_id=f"normal_execute_{state['index']}", enable_lock=enable_lock)
            return {
                "response": "执行智能体初始化失败",
                "past_steps": [task]
            }

        result = await normal_execute_agent.ainvoke(
            {"messages": [("user", formatted_task)]},
            {"recursion_limit": config["RECURSION_LIMIT"]},
        )

        messages = result.get("messages", None)
        if messages is None:
            await refresh_todo_list(state["index"], "fail", "执行任务完成，返回为空", task_id=f"normal_execute_{state['index']}", enable_lock=enable_lock)
            return {
                "response": "执行任务完成，返回为空",
                "past_steps": [task]
            }

        response = messages[-1].content
        await refresh_todo_list(state["index"], "done", response, task_id=f"normal_execute_{state['index']}", enable_lock=enable_lock)

        return {
            "past_achievement": [(task, response)],
            "past_steps": [task]
        }
    except Exception as e:
        logging.error(f"执行任务失败: {str(e)}")
        await refresh_todo_list(state["index"], "fail", f"执行任务失败: {str(e)}", task_id=f"normal_execute_{state['index']}", enable_lock=enable_lock)
        return {
            "response": f"执行任务失败: {str(e)}",
            "past_steps": [task]
        }

    finally:
        if enable_lock:
            clear_task_context()


async def code_execute_node(state: PlanExecute, enable_lock: bool = False) -> PlanExecute:
    """
    执行节点
    """
    # 延迟导入避免循环导入，并确保在函数执行时获取最新的 agent 值
    # from agent_instance import recommend_agent, recommend_check_agent
    from agent_instance import code_agent
    
    if not state["plan"] or not len(state["plan"]):
        return {
            "response": "没有计划，无需执行",
            "past_steps": []
        }

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

    logger.info("执行任务: %s", detailed_task)

    manager = None
    if enable_lock:
        manager = get_file_manager()
        set_task_context(f"code_execute_{state['index']}", manager)
    
    def write_development_log(response: str):
        with open(os.path.join(state["workspace"], "development_log.md"), "a", encoding="utf-8") as f:
            f.write(f"\n\n{response}")

    try:
        await refresh_todo_list(state["index"], "processing", task_id=f"code_execute_{state['index']}", enable_lock=enable_lock)
        result = await code_agent.ainvoke(
            {"messages": [("user", detailed_task)]},
            {"recursion_limit": config["RECURSION_LIMIT"]},
        )

        messages = result.get("messages", None)
        if messages is None:
            await refresh_todo_list(state["index"], "fail", "执行任务完成，返回为空", task_id=f"code_execute_{state['index']}", enable_lock=enable_lock)
            return {
                "response": "执行任务完成，返回为空",
                "past_steps": [task]
            }

        response = messages[-1].content
        await refresh_todo_list(state["index"], "done", response, task_id=f"code_execute_{state['index']}", enable_lock=enable_lock)
        
        if enable_lock:
            async with manager.write_lock(os.path.join(state["workspace"], "development_log.md"), f"code_execute_{state['index']}", timeout=10):
                await asyncio.to_thread(write_development_log, response)
        else:
            write_development_log(response)

        return {
            "past_achievement": [(task, response)],
            "past_steps": [task]
        }

    except Exception as e:
        logging.error(f"执行任务失败: {str(e)}")
        await refresh_todo_list(state["index"], "fail", f"执行任务失败: {str(e)}", task_id=f"code_execute_{state['index']}", enable_lock=enable_lock)
        return {
            "response": f"执行任务失败: {str(e)}",
            "past_steps": [task]
        }

    finally:
        if enable_lock:
            clear_task_context()


async def execute_node(state: PlanExecute) -> PlanExecute:
    """
    统一的执行节点（默认使用 code_execute_node）
    """
    steps = state.get("plan", [])
    index = state.get("index", 0)
    if len(steps) == 0:
        return {"response": "没有计划，无需执行"}

    task_list = steps.pop(0)
    
    enable_lock = False
    if len(task_list) > 1:
        enable_lock = True

    async_tasks = []
    for idx, task in enumerate(task_list):
        new_state = {
            "input": state["input"],
            "plan": [task],
            "past_achievement": state.get("past_achievement", []),
            "past_steps": state.get("past_steps", []),
            "index": index + idx,
            "response": state.get("response", ""),
            "workspace": state.get("workspace", "")
        }
        if "代码开发" in task:
            async_tasks.append(code_execute_node(new_state, enable_lock))
        else:
            async_tasks.append(normal_execute_node(new_state, enable_lock))

    results = await asyncio.gather(*async_tasks)
    response_state = {
        "response": "",
        "index": index + len(task_list),
        "past_achievement": state.get("past_achievement", []),
        "past_steps": state.get("past_steps", []),
        "plan": steps
    }
    
    for result in results:
        if "response" in result:
            task_wrapper = result.get("past_steps", [])

            if len(task) > 0:
                task = task_wrapper[0]
            else:
                task = ""
                task_wrapper = ["任务为空，无需执行"]
            
            response_state["past_achievement"].extend([(task, result.get("response", ""))])
            response_state["past_steps"].extend(task_wrapper)
            continue
        
        response_state["past_achievement"].extend(result.get("past_achievement", []))
        response_state["past_steps"].extend(result.get("past_steps", []))

    return response_state
