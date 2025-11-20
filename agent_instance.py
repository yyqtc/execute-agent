from langchain.agents import create_agent
from middleware import middlewares
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from custom_type import Plan, Act
from load_config import config
from middleware import middlewares

import logging
import asyncio

logger = logging.getLogger(__name__)

async def initialize_plan_model():
    """
    初始化计划模型并返回模型实例
    """
    try:
        return (ChatOpenAI(
            model=config.get("PLAN_LLM_MODEL", "qwen-plus"),
            openai_api_key=config["LLM_API_KEY"],
            openai_api_base=config["LLM_API_BASE"],
            temperature=0,
        ), "plan_model")
    except Exception as e:
        logger.error(f"错误: 计划用模型 初始化失败: {e}")
        return None

async def initialize_summary_model():
    """
    初始化总结用模型
    """
    try:
        return (ChatOpenAI(
            model=config.get("SUMMARY_LLM_MODEL", "qwen-plus"),
            openai_api_key=config["LLM_API_KEY"],
            openai_api_base=config["LLM_API_BASE"],
            temperature=0.3,
        ), "summary_model")
    except Exception as e:
        logger.error(f"错误: 总结用模型 初始化失败: {e}")
        return None

async def initialize_code_execute_model():
    """
    初始化执行用模型
    """
    try:
        return (ChatOpenAI(
            model=config.get("CODE_LLM_MODEL", "qwen-plus"),
            openai_api_key=config["LLM_API_KEY"],
            openai_api_base=config["LLM_API_BASE"],
            temperature=0.7,
        ), "code_model")
    except Exception as e:
        logger.error(f"错误: 执行用模型 初始化失败: {e}")
        return None

async def initialize_analysis_execute_model():
    """
    初始化执行用模型
    """
    try:
        return (ChatOpenAI(
            model=config.get("ANALYSIS_LLM_MODEL", "qwen-plus"),
            openai_api_key=config["LLM_API_KEY"],
            openai_api_base=config["LLM_API_BASE"],
            temperature=0.7,
        ), "analysis_model")
    except Exception as e:
        logger.error(f"错误: 执行用模型 初始化失败: {e}")
        return None

async def initialize_plan_agent(model, tools=[]):
    """
    初始化计划用智能体并返回 agent 实例
    """

    system_prompt = """
    你是一位擅长拆解任务的助手，擅长将一个复杂任务拆解为若干个简单的独立子任务。
    你需要根据用户的问题，输出一个计划，这个计划中应该包含若干个独立的子任务，子任务正确执行后，应该能够回答用户的问题。
    你输出的计划中每个步骤都不应该出现任何和答案有关的暗示。
    确保计划中的每一步都能够得到所有需要的信息。
    确保计划的最后一步输出的是对用户问题的最终答案。

    注意！
    1. 当用户使用系统字眼时，除非明确告诉你分析操作系统，否侧你默认分析当前文件夹。
    2. 你必须知道执行你的计划的是一个支持文件操作、代码搜索、终端命令执行、网络搜索等功能的开发团队！请不要让他们执行超出他们能力范围的命令！
    3. 你的指令必须是没有歧义的！不要让开发团队猜你的意思！
    4. 我们的预算非常有限！你的计划中不要包含重复的和不必要的步骤！
    5. 你必须谨慎修改、删除文件，因为这些操作都是不可逆的！
    6. 你返回的计划必须以JSON格式输出，包含steps字段，steps字段是一个数组，数组中每个元素是一个字符串，表示一个步骤。
    """
    if not model:
        model = initialize_plan_model()

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("user", "{input}"),
        ]
    )

    return (prompt | model.with_structured_output(Plan), "plan_agent")


async def initialize_replan_agent(model, tools=[]):
    """
    初始化再计划用智能体并返回 agent 实例
    """
    system_prompt = f"""
    你是一位善于理解需求的助手，善于根据计划执行情况分析当前计划是否符合客户需求。
    你只应该检查计划是否符合客户需求，而不应该指示开发团队做任何偏离客户需求的事情，比如：
        1. 客户让检查项目，你不应该指示开发团队去执行开发任务！
        2. 客户让开发程序，你不应该去修改用户指定的文件以外的文件！

    注意！
    1. 当用户使用系统字眼时，除非明确告诉你分析操作系统，否侧你默认分析当前文件夹。
    2. 你必须知道执行你的计划的是一个支持文件操作、代码搜索、终端命令执行、网络搜索等功能的开发团队！请不要让他们执行超出他们能力范围的命令！
    3. 开发团队不能胜任信息总结的任务！请不要把信息总结作为步骤加入到计划中！
    4. 你的指令必须是没有歧义的！不要让开发团队猜你的意思！
    5. 我们的预算非常有限！你的计划中不要包含重复的和不必要的步骤！
    6. 你必须谨慎修改、删除文件，因为这些操作都是不可逆的！
    7. 你不能删除或修改计划中已经存在的步骤！只能在已有计划基础上补充新的步骤！
    8. 你不允许将已经执行过的步骤补充进计划！
    9. 确保计划中的每一步都能够得到所有需要的信息。
    10. 确保计划的最后一步输出的是对用户问题的最终答案。
    11. 如果用户让你形成文件，你必须形成文件，不能只生成文本。
    12. 计划请以JSON格式输出，包含action字段，action字段应该包含steps字段，steps字段类型List[str]！
    13. 答案请以JSON格式输出，包含action字段，action字段应该包含response字段，response字段类型str！
    """
    if not model:
        model = initialize_plan_model()

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("user", "{input}"),
        ]
    )

    return (prompt | model.with_structured_output(Act), "replan_agent")


async def initialize_normal_execute_agent(model, tools=[]):
    """
    初始化非代码编写助手并返回 agent 实例
    """

    system_prompt = """
    你是一个非常专业的助手。你可以使用能力来完成任务。

    注意！
    1. 你必须在任务结束后，删除所有临时创建的文件！比如说测试用脚本！
    2. 你输出的代码中必须抑制除了异常信息、错误信息以及结果信息以外的所有打印！
    3. 你输出的代码中不准含有emoji！
    4. 你必须默认在所有的任务都是在当前这个目录下执行的！当然也包括这个目录的子目录！
    5. 删除文件、修改文件是不可逆的操作！必须谨慎使用！
    """
    if not model:
        model = initialize_execute_model()

    return (create_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=middlewares,
    ), "normal_execute_agent")


async def initialize_recommend_agent(model, tools=[]):
    system_prompt = """
    你是一名资深技术架构师，擅长把模糊需求拆成可落地的技术方案。

    我需要你按照以下步骤进行工作，并按顺序输出：
    1. 分析当前项目，理解完成任务需要的依赖以及项目的技术栈
    2. 用一句话概括的核心目标
    3. 列出 3–5 个关键子任务，并为每个子任务给出 1–2 句实现思路
    4. 推荐技术栈，并说明理由
    5. 输出一份伪代码或接口定义，不超过 20 行，主要用于说明实现思路
    6. 分析项目结构，确认新开发的功能应该放在哪个目录下，或是创建新的目录。尽量在已有目录下开发新功能。

    注意！
    1. 删除文件、修改文件是不可逆的操作！必须谨慎使用！
    2. 你应该确保引用依赖时的路径问题！否则项目将会失败！
    """

    return (create_agent(
        model=model, system_prompt=system_prompt, tools=tools, middleware=middlewares
    ), "recommend_agent")

async def initialize_recommend_check_agent(model, tools=[]):
    detailed_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""
                你是一名代码质量与需求澄清专家。请对上一步的方案做以下动作。
                - 逐条检查目标、子任务、技术栈、伪代码是否存在歧义、遗漏或风险
                - 针对每处问题，提出 1 个澄清问题或改进建议；
                - 把补充后的最终需求写成一段无歧义的自然语言，作为下一步的输入
                """,
            ),
            ("user", "{input}"),
        ]
    )

    return (detailed_prompt | model, "recommend_check_agent")


async def initialize_code_agent(model, tools=[]):
    """
    初始化智能体并返回 agent 实例
    """
    if not model:
        model = initialize_execute_model()

    system_prompt = """
    你是一个非常专业的全栈开发工程师，严格按照最终需求生成可运行代码。你可以使用能力来完成任务。要求：
    1. 按模块生成完整代码，每个文件用 ```lang 开头注明语言
    2. 关键函数需加 1–2 行注释；
    3. 如遇未明确的参数，用 TODO: 标出并给出默认值

    注意！
    1. 你必须在任务结束后，删除所有测试用脚本！
    2. 你输出的代码中必须抑制除了异常信息、错误信息以及结果信息以外的所有打印！
    3. 你输出的代码中不准含有emoji！
    4. 你写完代码后必须保证 **每一行代码** 都没有逻辑问题和语法问题！
    5. 除了测试用脚本，你必须谨慎删除、修改任何文件！
    """

    return (create_agent(
        model=model, system_prompt=system_prompt, tools=tools, middleware=middlewares
    ), "code_agent")


async def initialize_assistant_choose_agent(model, tools=[]):
    """
    初始化路由智能体并返回 agent 实例
    """
    if not model:
        model = initialize_plan_model()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""
                你是一位专业的助手，请判断当前任务是否是代码开发任务，代码迁移任务不算代码开发任务。如果是，则返回"code_execute"，否则返回"normal_execute"。
                """,
            ),
            ("user", "{input}"),
        ]
    )

    return (prompt | model, "assistant_choose_agent")


async def initialize_summary_agent(model, tools=[]):
    """
    初始化总结智能体并返回 agent 实例
    """
    if not model:
        model = initialize_summary_model()

    summary_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""
                你是一位非常专业的总结专家，善于抓住项目日志中的重点内容。请把项目日志的字数控制在{config["SUMMARY_MAX_LENGTH"]}个token以内。
                注意！
                尽量保留日志中的重要信息，适当压缩其他信息，不要遗漏重要信息！
                """,
            ),
            ("user", "{input}"),
        ]
    )

    return (summary_prompt | model, "summary_agent")


# 全局 agent 变量，初始化为 None，在 initial_agent() 中初始化
plan_agent = None
replan_agent = None
normal_execute_agent = None
recommend_agent = None
recommend_check_agent = None
code_agent = None
assistant_choose_agent = None
summary_agent = None

async def initial_agent(tools):
    model_initial_tasks = [
        initialize_plan_model(),
        initialize_summary_model(),
        initialize_code_execute_model(),
        initialize_analysis_execute_model(),
    ]
    model_initial_results = await asyncio.gather(*model_initial_tasks)
    model_map = {}
    for result in model_initial_results:
        if result is None:
            continue
        if result[1] == "plan_model":
            model_map["plan_model"] = result[0]
        elif result[1] == "summary_model":
            model_map["summary_model"] = result[0]
        elif result[1] == "code_model":
            model_map["code_model"] = result[0]
        elif result[1] == "analysis_model":
            model_map["analysis_model"] = result[0]

    agent_initial_tasks = [
        initialize_plan_agent(model_map["plan_model"]),
        initialize_replan_agent(model_map["plan_model"]),
        initialize_normal_execute_agent(model_map["analysis_model"], tools),
        initialize_recommend_agent(model_map["plan_model"], tools),
        initialize_recommend_check_agent(model_map["analysis_model"]),
        initialize_code_agent(model_map["code_model"], tools),
        initialize_assistant_choose_agent(model_map["plan_model"]),
        initialize_summary_agent(model_map["summary_model"])
    ]
    agent_initial_results = await asyncio.gather(*agent_initial_tasks)
    for result in agent_initial_results:
        if result is None:
            continue
        if result[1] == "plan_agent":
            global plan_agent
            plan_agent = result[0]
        elif result[1] == "replan_agent":
            global replan_agent
            replan_agent = result[0]
        elif result[1] == "normal_execute_agent":
            global normal_execute_agent
            normal_execute_agent = result[0]
        elif result[1] == "recommend_agent":
            global recommend_agent
            recommend_agent = result[0]
        elif result[1] == "recommend_check_agent":
            global recommend_check_agent
            recommend_check_agent = result[0]
        elif result[1] == "code_agent":
            global code_agent
            code_agent = result[0]
        elif result[1] == "assistant_choose_agent":
            global assistant_choose_agent
            assistant_choose_agent = result[0]
        elif result[1] == "summary_agent":
            global summary_agent
            summary_agent = result[0]
