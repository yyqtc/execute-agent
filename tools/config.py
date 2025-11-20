import logging

logger = logging.getLogger(__name__)

import os
import json
from pathlib import Path


def get_config():
    """
    从环境变量或配置文件读取配置

    Returns:
        dict: 包含配置的字典，例如 {"BOCHA_API_KEY": "..."}

    Raises:
        ValueError: 当配置读取失败或API密钥未设置时抛出
    """
    bocha_api_key = os.getenv("BOCHA_API_KEY")
    # 如果环境变量为空字符串，设置为 None
    if bocha_api_key == "":
        bocha_api_key = None
    # 尝试从配置文件读取配置
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.json"
        )
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        # 如果环境变量中没有 API 密钥，从配置文件读取
        if not bocha_api_key:
            bocha_api_key = config.get("BOCHA_API_KEY")
            # 如果 API 密钥为空字符串，则设置为 None
            if bocha_api_key == "":
                bocha_api_key = None
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误: {str(e)}")

    if not bocha_api_key:
        raise ValueError(
            "BOCHA_API_KEY 未设置。请设置环境变量 BOCHA_API_KEY 或在 config.json 中配置。"
        )

    return {"BOCHA_API_KEY": bocha_api_key}
