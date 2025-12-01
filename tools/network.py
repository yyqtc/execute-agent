import json
import logging
import requests

from .config import get_config

logger = logging.getLogger(__name__)


def web_search(
    query: str, freshness: str = "noLimit", summary: bool = True, count: int = 50
) -> str:
    """
    使用博查API进行网络搜索

    Args:
        query: 搜索查询字符串
        freshness: 新鲜度过滤，可选值: "noLimit", "pastDay", "pastWeek", "pastMonth", "pastYear"
        summary: 是否返回摘要
        count: 返回结果数量，默认50

    Returns:
        JSON格式的搜索结果字符串
    """
    try:
        # 获取API密钥配置
        try:
            config = get_config()
            api_key = config.get("BOCHA_API_KEY")
        except ValueError as e:
            # 处理配置错误（API密钥未设置等）
            return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)

        if not api_key:
            return json.dumps(
                {"error": "BOCHA_API_KEY未配置"}, ensure_ascii=False, indent=2
            )

        # 构建请求
        url = "https://api.bochaai.com/v1/ai-search"
        payload = {
            "query": query,
            "freshness": freshness,
            "summary": summary,
            "count": count,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 发送请求
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        # 返回响应
        if response.status_code == 200:
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        else:
            return json.dumps(
                {
                    "error": f"API请求失败，状态码: {response.status_code}",
                    "response": response.text,
                },
                ensure_ascii=False,
                indent=2,
            )

    except requests.exceptions.Timeout:
        return json.dumps({"error": "请求超时"}, ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        return json.dumps(
            {"error": f"网络请求错误: {str(e)}"}, ensure_ascii=False, indent=2
        )
    except Exception as e:
        return json.dumps(
            {"error": f"未知错误: {str(e)}"}, ensure_ascii=False, indent=2
        )
