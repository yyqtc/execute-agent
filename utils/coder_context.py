import os
import asyncio
import logging
from load_config import config

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