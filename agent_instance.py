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
            temperature=0.3,
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
            temperature=0.3,
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
            temperature=0.3,
        ), "analysis_model")
    except Exception as e:
        logger.error(f"错误: 执行用模型 初始化失败: {e}")
        return None

async def initialize_plan_agent(model, tools=[]):
    """
    初始化计划用智能体并返回 agent 实例
    """

    system_prompt = """
    你是一位擅长拆解任务的助手，擅长将一个复杂任务拆解为若干个简单的独立子任务，并标识其中可以并行执行的任务。拆分任务时保持适度（同一分组内任务数量不超过3个）的并行化策略。
    你需要根据用户的问题，输出一个计划，这个计划中应该包含若干个独立的子任务，子任务正确执行后，应该能够回答用户的问题。
    你输出的计划中每个步骤都不应该出现任何和答案有关的暗示。
    确保计划中的每一步都能够得到所有需要的信息。
    确保计划的最后一步输出的是对用户问题的最终答案。
    指定任务时，必须将团队名称作为前缀，比如“日常助手团队: ”和“代码开发团队: ”

    并行任务使用时机和标记格式解释：
    1. 如果某些任务之间没有依赖关系，可以同时执行，请在任务开头加上[PARALLEL-X]标记：
      - [PARALLEL-X]中的X是分组编号（X=1,2,3,...）
      - 相同分组编号的任务的任务应该支持并行执行，相同分组编号的任务之间不应该存在依赖关系
      - 不同分组编号的任务之间必须是顺序执行，并且必须保证分组编号大的任务所需要的信息可以在分组编号小的任务执行完成后得到
      - 如果一个任务和其他任务没有并行关系，也必须在任务开头加上分组编号。

    并行任务用例：
    - 用户：“帮我写一个Python程序，程序的功能是：1. 读取一个文本文件，2. 统计文本文件中每个单词出现的次数，3. 将统计结果写入一个JSON文件。”
    - 输出：
    {{
        "steps": [
            "[PARALLEL-1] 日常助手团队: 确认文本文件的路径和文件名。",
            "[PARALLEL-1] 日常助手团队: 确定输出JSON文件的目标路径及文件名。",
            "[PARALLEL-2] 代码开发团队: 编写读取文本文件内容的功能模块，确保能够正确处理指定路径下的文件。",
            "[PARALLEL-2] 代码开发团队: 编写将给定的单词计数字典序列化并写入到指定JSON文件的功能模块。",
            "[PARALLEL-3] 日常助手团队: 使用已开发的功能模块测试读取功能，确保能准确无误地读取指定文本文件的内容，并将结果反馈给代码开发团队。",
            "[PARALLEL-4] 代码开发团队: 根据日常助手团队提供的反馈，调整并优化读取文本文件内容的功能模块。",
            "[PARALLEL-5] 日常助手团队: 准备测试用例，包括文本文件中可能包含的单词及其预期出现次数，用于后续功能验证。",
            "[PARALLEL-6] 代码开发团队: 编写统计文本文件中每个单词出现次数的功能模块，该模块需要接受一个字符串作为输入，并返回一个字典，字典的键是单词，值是该单词在输入字符串中出现的次数。",
            "[PARALLEL-7] 日常助手团队: 结合准备好的测试用例，对单词统计功能进行测试，确保统计准确性，并将测试结果反馈给代码开发团队。",
            "[PARALLEL-8] 代码开发团队: 根据日常助手团队提供的反馈，调整并优化单词统计功能模块。",
            "[PARALLEL-9] 日常助手团队: 对整个程序（从读取文件、统计单词到输出JSON）进行全面测试，确保所有功能按预期工作。",
            "[PARALLEL-10] 日常助手团队: 最终检查并确认输出的JSON文件格式正确且数据准确。"
        ]
    }}

    - 执行流程：
      1. PARALLEL-1的两个任务可以同时执行。
      2. PARALLEL-2的两个任务可以同时执行。
      3. PARALLEL-3之后的任务顺序执行。

    没有并行任务用例：
    用户："分析这个 bug 的原因，并修改bug"

    输出：
    {{
        "steps": [
            "[PARALLEL-1] 日常助手团队: 读取错误日志和报错信息",
            "[PARALLEL-2] 日常助手团队: 定位出错的代码位置",
            "[PARALLEL-3] 日常助手团队: 分析代码逻辑找出问题根源",
            "[PARALLEL-4] 日常助手团队: 提供修复建议"
            "[PARALLEL-5] 代码开发团队: 根据修复建议，编写修复代码"
        ]
    }}

    （所有任务都有依赖关系，无法并行）

    什么时候使用并行标记？
    ✓ 为不同模块/文件编写代码
    ✓ 为不同模块编写测试
    ✓ 分析多个独立文件
    ✓ 处理多个独立数据集
    ✓ 生成多个独立文档

    不能并行的场景:
    ✗ 任务之间有依赖（如：先分析再编写）
    ✗ 需要顺序执行（如：先创建再修改）
    ✗ 共享同一资源（如：同时修改同一文件）

    注意！
    1. 当用户使用系统字眼时，除非明确告诉你分析操作系统，否侧你默认分析当前文件夹。
    2. 有两个团队执行你的计划，一个是日常助手团队，一个是代码开发团队。
    3. 日常助手团队支持文件操作、代码搜索、终端命令执行、网络搜索等功能。但是他们不负责写代码！日常助手团队可以帮助你分析项目，以及测试项目。日常助手团队不能执行网页浏览和操作的行为，不能使用浏览器！
    4. 代码开发团队只负责写代码，不负责文件操作、代码搜索、执行终端、网络搜索等功能。不要让代码开发团队干除了写代码以外的任何事情！
    5. 你的指令必须是没有歧义的！不要让开发团队猜你的意思！
    6. 我们的预算非常有限！你的计划中不要包含重复的和不必要的步骤！
    7. 你必须谨慎修改、删除文件，因为这些操作都是不可逆的！
    8. 你必须优先识别可并行的任务（提高效率）！但是任务尽量保证能够调用在1个工具后得到结果。
    9. 你返回的计划必须以JSON格式输出，包含steps字段，steps字段是一个数组，数组中每个元素是一个字符串，表示一个步骤。
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

    system_prompt = """
    你是一位善于理解需求的助手，你需要根据用户的问题，分析当前计划执行情况和接下来的计划是否能完成用户需求。如果不能完成用户需求，你需要更新计划，并标识其中可以并行执行的任务。拆分任务时保持适度（同一分组内任务数量不超过3个）的并行化策略。
    你的职责是确保用户交代的任务完全实现。

    并行任务使用时机和标记格式解释：
    1. 如果某些任务之间没有依赖关系，可以同时执行，请在任务开头加上[PARALLEL-X]标记：
      - [PARALLEL-X]中的X是分组编号（X=1,2,3,...）
      - 相同分组编号的任务的任务应该支持并行执行，相同分组编号的任务之间不应该存在依赖关系
      - 不同分组编号的任务之间必须是顺序执行，并且必须保证分组编号大的任务所需要的信息可以在分组编号小的任务执行完成后得到
      - 如果一个任务和其他任务没有并行关系，也必须在任务开头加上分组编号。

    并行任务用例：
    - 用户：“帮我写一个Python程序，程序的功能是：1. 读取一个文本文件，2. 统计文本文件中每个单词出现的次数，3. 将统计结果写入一个JSON文件。”
    - 输出：
    {{
        "steps": [
            "[PARALLEL-1] 日常助手团队: 确认文本文件的路径和文件名。",
            "[PARALLEL-1] 日常助手团队: 确定输出JSON文件的目标路径及文件名。",
            "[PARALLEL-2] 代码开发团队: 编写读取文本文件内容的功能模块，确保能够正确处理指定路径下的文件。",
            "[PARALLEL-2] 代码开发团队: 编写将给定的单词计数字典序列化并写入到指定JSON文件的功能模块。",
            "[PARALLEL-3] 日常助手团队: 使用已开发的功能模块测试读取功能，确保能准确无误地读取指定文本文件的内容，并将结果反馈给代码开发团队。",
            "[PARALLEL-4] 代码开发团队: 根据日常助手团队提供的反馈，调整并优化读取文本文件内容的功能模块。",
            "[PARALLEL-5] 日常助手团队: 准备测试用例，包括文本文件中可能包含的单词及其预期出现次数，用于后续功能验证。",
            "[PARALLEL-6] 代码开发团队: 编写统计文本文件中每个单词出现次数的功能模块，该模块需要接受一个字符串作为输入，并返回一个字典，字典的键是单词，值是该单词在输入字符串中出现的次数。",
            "[PARALLEL-7] 日常助手团队: 结合准备好的测试用例，对单词统计功能进行测试，确保统计准确性，并将测试结果反馈给代码开发团队。",
            "[PARALLEL-8] 代码开发团队: 根据日常助手团队提供的反馈，调整并优化单词统计功能模块。",
            "[PARALLEL-9] 日常助手团队: 对整个程序（从读取文件、统计单词到输出JSON）进行全面测试，确保所有功能按预期工作。",
            "[PARALLEL-10] 日常助手团队: 最终检查并确认输出的JSON文件格式正确且数据准确。"
        ]
    }}

    - 执行流程：
      1. PARALLEL-1的两个任务可以同时执行。
      2. PARALLEL-2的两个任务可以同时执行。
      3. PARALLEL-3之后的任务顺序执行。

    没有并行任务用例：
    用户："分析这个 bug 的原因，并修改bug"

    输出：
    {{
        "steps": [
            "[PARALLEL-1] 日常助手团队: 读取错误日志和报错信息",
            "[PARALLEL-2] 日常助手团队: 定位出错的代码位置",
            "[PARALLEL-3] 日常助手团队: 分析代码逻辑找出问题根源",
            "[PARALLEL-4] 日常助手团队: 提供修复建议"
            "[PARALLEL-5] 代码开发团队: 根据修复建议，编写修复代码"
        ]
    }}

    （所有任务都有依赖关系，无法并行）

    什么时候使用并行标记？
    ✓ 为不同模块/文件编写代码
    ✓ 为不同模块编写测试
    ✓ 分析多个独立文件
    ✓ 处理多个独立数据集
    ✓ 生成多个独立文档

    不能并行的场景:
    ✗ 任务之间有依赖（如：先分析再编写）
    ✗ 需要顺序执行（如：先创建再修改）
    ✗ 共享同一资源（如：同时修改同一文件）

    注意！
    1. 当用户使用系统字眼时，除非明确告诉你分析操作系统，否侧你默认分析当前文件夹。
    2. 有两个团队执行你的计划，一个是日常助手团队，一个是代码开发团队。
    3. 日常助手团队支持文件操作、代码搜索、终端命令执行、网络搜索等功能。但是他们不负责写代码！日常助手团队可以帮助你分析项目，以及测试项目。日常助手团队不能执行网页浏览和操作的行为，不能使用浏览器！
    4. 代码开发团队只负责写代码，不负责文件操作、代码搜索、执行终端、网络搜索等功能。不要让代码开发团队干除了写代码以外的任何事情！
    5. 你的指令必须是没有歧义的！不要让开发团队猜你的意思！
    6. 我们的预算非常有限！你的计划中不要包含重复的步骤！
    7. 你必须谨慎修改、删除文件，因为这些操作都是不可逆的！
    8. 你必须优先识别可并行的任务（提高效率）！但是任务尽量保证能够调用在1个工具后得到结果。
    9. 你不能删除或修改计划中已经存在的步骤！只能在已有计划基础上补充新的步骤！
    10. 你不允许将已经执行过的步骤补充进计划！你不允许将已经执行过的步骤补充进计划！你不允许将已经执行过的步骤补充进计划！你不允许将已经执行过的步骤补充进计划！你不允许将已经执行过的步骤补充进计划！你不允许将已经执行过的步骤补充进计划！
    11. 如果用户让你形成文件，你必须形成文件，不能只生成文本。
    12. 你输出的计划中每个步骤都不应该出现任何和答案有关的暗示。
    13. 确保计划中的每一步都能够得到所有需要的信息。
    14. 确保计划的最后一步输出的是对用户问题的最终答案。
    15. 指定任务时，必须将团队名称作为前缀，比如“日常助手团队: ”和“代码开发团队: ”
    16. 并行数根据任务实际需求为主，可以是2,3,4,...
    17. 计划请以JSON格式输出，包含action字段，action字段应该包含steps字段，steps字段类型List[str]！
    18. 答案请以JSON格式输出，包含action字段，action字段应该包含response字段，response字段类型str！
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
    1. 你必须在任务结束后，删除所有创建的空文件夹和测试脚本！比如说测试用脚本！
    2. 你输出的代码中必须抑制除了异常信息、错误信息以及结果信息以外的所有打印！
    3. 你输出的代码中不准含有emoji！
    4. 你必须默认在所有的任务都是在当前这个目录下执行的！当然也包括这个目录的子目录！
    5. 删除文件、修改文件是不可逆的操作！必须谨慎使用！
    6. 任务中让你分析代码，优先使用python的ast进行分析！只有明确告诉你需要测试代码是否存在bug时，才使用read_lints方法！
    7. 你需要将你的实现结果更新到development_log.md文件中，更新到development_log.md文件中的内容必须是具体到如何思考的和如何实现的！
    8. 在你尝试写内容进development_log.md文件前，你必须先检查文件是否存在，如果文件不存在，则创建文件，如果文件存在，则更新文件内容而不要直接覆盖！
    9. 请尽量在一次response中调用多个工具，而不要一次只调用一个工具！
    """
    if not model:
        model = initialize_analysis_execute_model()

    return (create_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=middlewares,
    ), "normal_execute_agent")


async def initialize_code_agent(model, tools=[]):
    """
    初始化智能体并返回 agent 实例
    """
    if not model:
        model = initialize_code_execute_model()

    system_prompt = """
    你是一个非常专业的全栈开发工程师，严格按照最终需求生成可运行代码。你可以使用能力来完成任务。要求：
    1. 按模块生成完整代码，每个文件用 ```lang 开头注明语言
    2. 关键函数需加 1–2 行注释；
    3. 如遇未明确的参数，用 TODO: 标出并给出默认值

    UI/UX设计要求（当生成Web页面或前端界面时）：
    1. 必须创建美观、现代化的用户界面，遵循现代Web设计最佳实践
    2. 使用现代化的CSS框架（如Tailwind CSS、Bootstrap等）或精心设计的自定义样式
    3. 确保界面具有良好的视觉层次结构：使用合适的间距、对齐、字体大小和颜色对比度
    4. 实现响应式设计，确保在不同屏幕尺寸下都能良好显示
    5. 使用现代化的配色方案：避免过于鲜艳或刺眼的颜色，优先使用柔和的渐变色、阴影和圆角
    6. 添加适当的交互效果：按钮悬停效果、过渡动画、加载状态等，提升用户体验
    7. 确保良好的可访问性：使用语义化HTML、适当的ARIA标签、合理的焦点管理
    8. 布局要清晰整洁：使用网格系统、卡片式布局、合理的留白空间
    9. 如果使用CSS，优先使用现代CSS特性（Flexbox、Grid、CSS变量等）
    10. 图标和视觉元素要统一风格，可以使用图标库（如Font Awesome、Heroicons等）
    11. 尽量使用成熟组件库构建页面，如Element UI、Ant Design、Naive UI等

    在生成Vue项目时:
    1. 组件名称必须使用多个单词按照驼峰命名法命名
    2. 每个组件/模块只负责一个明确的功能
    3. 优先使用 TypeScript，提供强类型保障，减少运行时错误；如果当前项目使用JavaScript，则保持一致性使用JavaScript
    4. 接口定义清晰，使用TypeScript时提供完整的类型定义
    5. 优先使用 Vue 3 Composition API（<script setup>），代码更简洁、逻辑更清晰
    6. 使用组合式函数（Composables）抽离可复用的业务逻辑，保持组件代码简洁
    7. 不是所有状态都需要放进 store（Pinia/Vuex）。组件内部状态应保留在组件内，只有组件间共享的状态才需要放进 store
    8. 输入搜索实现防抖特性，不要每次输入都请求接口
    9. 触发频率极高的操作（如滚动）实现节流特性
    10. 完善全局错误捕获：使用 app.config.errorHandler 进行全局错误处理，在组件中使用 errorCaptured 钩子捕获子组件错误
    11. 编写代码时必须遵守eslint规范，关键功能建议编写单元测试（使用Vitest或Jest）
    12. 防 XSS：Vue 模板自动转义，但避免 v-html；如必须用，需 DOMPurify 过滤
    13. 配置信息写到环境变量，避免硬编码
    14. 前端在vue-router中必须实现路由守卫，严格按照用户的权限执行路由跳转
    15. 路由懒加载：使用动态 import() 实现路由组件的按需加载，提升首屏加载速度
    16. 列表渲染优化：大数据列表使用虚拟滚动（如 vue-virtual-scroller），避免渲染过多DOM节点
    17. 合理使用 v-show 和 v-if：频繁切换用 v-show，条件很少改变用 v-if
    18. 使用 computed 和 watch 时注意性能，避免不必要的重复计算
    19. 组件通信：父子用 props/emit，跨级用 provide/inject，全局用 store
    20. 使用组件库时，优先使用组件库提供的主题定制功能，保持整体风格统一

    在生成React项目时：
    1. 避免传统的 components/, pages/, utils/ 扁平结构，推荐按业务域分层
    2. 关注点分离：
      - UI 组件（Presentational）：只负责渲染，接收 props，无状态
      - 容器组件（Container）：处理数据获取、状态管理，传递给 UI 组件
      - 现代演进：用 Custom Hooks 抽离逻辑，组件保持"纯渲染"
    3. 优先使用 TypeScript，提供强类型保障，减少运行时错误；如果当前项目使用JavaScript，则保持一致性使用JavaScript
    4. 文件命名、组件命名必须使用多个单词按照驼峰命名法命名
    5. 使用 ErrorBoundary 组件捕获组件树中的错误，提供友好的错误提示
    6. 输入搜索实现防抖特性，触发频率极高的操作（如滚动）实现节流特性
    7. 防 XSS：React 默认转义，避免 dangerouslySetInnerHTML；如必须用，需 DOMPurify 过滤
    8. 配置信息写到环境变量，避免硬编码

    注意！
    1. 你必须在任务结束后，删除所有测试用脚本！
    2. 你输出的代码中必须抑制除了异常信息、错误信息以及结果信息以外的所有打印！
    3. 你输出的代码中不准含有emoji！
    4. 你输出代码时务必保证代码的鲁棒性和准确性！
    5. 除了测试用脚本，你必须谨慎删除、修改任何文件！
    6. 请尽量在一次response中调用多个工具，而不要一次只调用一个工具！
    7. 你应该先学习gitee中相似功能是如何实现的，然后再生成代码！
    8. 当生成Web应用时，必须创建一个美观且现代化的界面，不要生成简陋或丑陋的页面！
    9. 你在编码前必须通过gitee查询相似功能是如何实现的，然后再生成代码！
    """

    return (create_agent(
        model=model, system_prompt=system_prompt, tools=tools, middleware=middlewares
    ), "code_agent")


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
                重要信息包括：未完成的功能、项目的结构、项目的依赖、项目中未解决的错误。
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
        initialize_code_agent(model_map["code_model"], tools),
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
        elif result[1] == "code_agent":
            global code_agent
            code_agent = result[0]
        elif result[1] == "summary_agent":
            global summary_agent
            summary_agent = result[0]
