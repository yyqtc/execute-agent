import os
import json
from typing import Optional


def _get_env_or_none(key: str) -> Optional[str]:
    """从环境变量获取值，空字符串转换为 None"""
    value = os.getenv(key)
    return None if value == "" else value


def _get_int_from_env(key: str) -> Optional[int]:
    """从环境变量获取整数值"""
    value = _get_env_or_none(key)
    if value is not None:
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _get_config():
    """从环境变量或配置文件读取配置
    
    优先级：环境变量 > 配置文件 > 默认值
    """
    # 从环境变量读取配置
    llm_api_key = _get_env_or_none("LLM_API_KEY")
    llm_api_base = _get_env_or_none("LLM_API_BASE")
    context7_api_key = _get_env_or_none("CONTEXT7_API_KEY")
    bocha_api_key = _get_env_or_none("BOCHA_API_KEY")
    gitee_token = _get_env_or_none("GITEE_TOKEN")
    recursion_limit = _get_int_from_env("RECURSION_LIMIT")
    
    # LLM 模型配置
    plan_llm_model = _get_env_or_none("PLAN_LLM_MODEL")
    summary_llm_model = _get_env_or_none("SUMMARY_LLM_MODEL")
    analysis_llm_model = _get_env_or_none("ANALYSIS_LLM_MODEL")
    code_llm_model = _get_env_or_none("CODE_LLM_MODEL")
    
    # 从配置文件读取配置
    config_file = {}
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    try:
        with open(config_path, encoding="utf-8") as f:
            config_file = json.load(f)
    except FileNotFoundError:
        print("警告: 配置文件 config.json 不存在，仅使用环境变量和默认值")
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误: {str(e)}")
    
    # 如果环境变量中没有，从配置文件读取
    if not llm_api_key:
        llm_api_key = config_file.get("LLM_API_KEY")
        if llm_api_key == "":
            llm_api_key = None
    
    if llm_api_base is None:
        llm_api_base = config_file.get("LLM_API_BASE")
        if llm_api_base == "":
            llm_api_base = None
    
    if not context7_api_key:
        context7_api_key = config_file.get("CONTEXT7_API_KEY")
        if context7_api_key == "":
            context7_api_key = None
    
    if not bocha_api_key:
        bocha_api_key = config_file.get("BOCHA_API_KEY")
        if bocha_api_key == "":
            bocha_api_key = None
    
    if not gitee_token:
        gitee_token = config_file.get("GITEE_TOKEN")
        if gitee_token == "":
            gitee_token = None
    
    if recursion_limit is None:
        recursion_limit = config_file.get("RECURSION_LIMIT")
        if recursion_limit is not None:
            try:
                recursion_limit = int(recursion_limit)
            except (ValueError, TypeError):
                recursion_limit = None
    
    # LLM 模型配置
    if not plan_llm_model:
        plan_llm_model = config_file.get("PLAN_LLM_MODEL")
        if plan_llm_model == "":
            plan_llm_model = None
    
    if not summary_llm_model:
        summary_llm_model = config_file.get("SUMMARY_LLM_MODEL")
        if summary_llm_model == "":
            summary_llm_model = None
    
    if not analysis_llm_model:
        analysis_llm_model = config_file.get("ANALYSIS_LLM_MODEL")
        if analysis_llm_model == "":
            analysis_llm_model = None
    
    if not code_llm_model:
        code_llm_model = config_file.get("CODE_LLM_MODEL")
        if code_llm_model == "":
            code_llm_model = None
    
    # 从配置文件读取其他配置
    summary_max_length = config_file.get("SUMMARY_MAX_LENGTH")
    summary_threshold = config_file.get("SUMMARY_THRESHOLD")
    
    # 设置默认值
    if llm_api_base is None:
        llm_api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    if recursion_limit is None:
        recursion_limit = 1000
    
    if not plan_llm_model:
        plan_llm_model = "qwen-plus"
    else:
        plan_llm_model = str(plan_llm_model)
    
    if not summary_llm_model:
        summary_llm_model = "qwen-plus"
    else:
        summary_llm_model = str(summary_llm_model)
    
    if not analysis_llm_model:
        analysis_llm_model = "qwen-plus"
    else:
        analysis_llm_model = str(analysis_llm_model)
    
    if not code_llm_model:
        code_llm_model = "qwen-plus"
    else:
        code_llm_model = str(code_llm_model)
    
    # 处理整数配置的默认值
    if summary_max_length is None:
        summary_max_length = 4000
    else:
        try:
            summary_max_length = int(summary_max_length)
        except (ValueError, TypeError):
            summary_max_length = 4000
    
    if summary_threshold is None:
        summary_threshold = 10000
    else:
        try:
            summary_threshold = int(summary_threshold)
        except (ValueError, TypeError):
            summary_threshold = 10000
    
    # 验证必需的配置
    if not llm_api_key:
        raise ValueError(
            "LLM_API_KEY 未设置。请设置环境变量 LLM_API_KEY 或在 config.json 中配置。"
        )
    
    # 构建配置字典
    result = {
        "PLAN_LLM_MODEL": plan_llm_model,
        "SUMMARY_LLM_MODEL": summary_llm_model,
        "ANALYSIS_LLM_MODEL": analysis_llm_model,
        "CODE_LLM_MODEL": code_llm_model,
        "LLM_API_KEY": llm_api_key,
        "LLM_API_BASE": llm_api_base,
        "RECURSION_LIMIT": recursion_limit,
        "SUMMARY_MAX_LENGTH": summary_max_length,
        "SUMMARY_THRESHOLD": summary_threshold,
    }
    
    # 可选配置（不强制要求）
    if context7_api_key:
        result["CONTEXT7_API_KEY"] = context7_api_key
    
    if bocha_api_key:
        result["BOCHA_API_KEY"] = bocha_api_key
    
    if gitee_token:
        result["GITEE_TOKEN"] = gitee_token
    
    return result


config = _get_config()
