import logging

import os
import sys
import json
from pathlib import Path

logger = logging.getLogger(__name__)


def create_langchain_mcp_client():
    """
    以docs.langchain.com为示例，创建 LangChain MCP 客户端

    Returns:
        MultiServerMCPClient: LangChain MCP 客户端
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as e:
        error_msg = (
            f"无法导入 MultiServerMCPClient: {str(e)}. "
            "请确保已安装 langchain_mcp_adapters 库。"
        )
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ImportError(error_msg) from e

    client = MultiServerMCPClient(
        {
            "server_name": {
                "url": "https://docs.langchain.com/mcp",
                "transport": "streamable_http",
            }
        }
    )

    return client


def create_context7_mcp_client():
    """
    创建连接至 Context7 MCP 服务的客户端。

    该函数会从环境变量或配置文件中读取 CONTEXT7_API_KEY，并使用该密钥
    创建并返回 MultiServerMCPClient 实例。配置优先级：环境变量 > config.json。

    MCP Server: https://mcp.context7.com/mcp
    认证方式: Bearer Token (CONTEXT7_API_KEY)

    Returns:
        MultiServerMCPClient: Context7 MCP 客户端实例

    Raises:
        ImportError: 当无法导入 MultiServerMCPClient 时抛出
        ValueError: 当 CONTEXT7_API_KEY 未配置或为空时抛出
        ConnectionError: 当无法连接到 MCP 服务器时抛出
        Exception: 当创建客户端时发生其他错误时抛出

    功能说明:
        - 首先尝试从环境变量 CONTEXT7_API_KEY 读取 API 密钥
        - 如果环境变量不存在，则从项目根目录下的 config.json 文件中读取
        - 如果两种方式都未找到密钥，抛出 ValueError 异常
        - 使用获取的 API 密钥创建 MultiServerMCPClient 实例
        - 配置 Bearer Token 认证头
        - 处理各种可能的错误情况（密钥缺失、配置文件读取失败、连接失败等）

    示例:
        >>> client = create_context7_mcp_client()
        >>> tools = await client.get_tools()
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as e:
        error_msg = (
            f"无法导入 MultiServerMCPClient: {str(e)}. "
            "请确保已安装 langchain_mcp_adapters 库。"
        )
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ImportError(error_msg) from e

    api_key = None
    config_error = None

    # 首先尝试从环境变量获取 API 密钥
    api_key = os.getenv("CONTEXT7_API_KEY")

    # 如果环境变量中没有，从 config.json 读取
    if not api_key:
        try:
            config_path = Path(__file__).parent.parent / "config.json"

            if not config_path.exists():
                config_error = f"配置文件不存在: {config_path}"
            else:
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        api_key = config.get("CONTEXT7_API_KEY")

                        if api_key and not isinstance(api_key, str):
                            config_error = (
                                "CONTEXT7_API_KEY 在配置文件中必须是字符串类型"
                            )
                            api_key = None
                except json.JSONDecodeError as e:
                    config_error = f"配置文件格式错误: {str(e)}"
                except IOError as e:
                    config_error = f"读取配置文件失败: {str(e)}"
        except Exception as e:
            config_error = f"处理配置文件时发生错误: {str(e)}"

    # 验证 API 密钥
    if not api_key:
        error_msg = (
            "CONTEXT7_API_KEY 未设置。请设置环境变量 CONTEXT7_API_KEY "
            "或在 config.json 中配置 CONTEXT7_API_KEY。"
        )
        if config_error:
            error_msg += f" 配置文件错误: {config_error}"
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ValueError(error_msg)

    # 去除 API 密钥首尾空白
    api_key = api_key.strip()

    if not api_key:
        error_msg = "CONTEXT7_API_KEY 不能为空"
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ValueError(error_msg)

    # 创建 MultiServerMCPClient 实例（使用 HTTP 传输）
    try:
        client = MultiServerMCPClient(
            {
                "context7": {
                    "url": "https://mcp.context7.com/mcp",
                    "transport": "streamable_http",
                    "headers": {"Authorization": f"Bearer {api_key}"},
                }
            }
        )
    except Exception as e:
        error_msg = f"创建 Context7 MCP 客户端失败: {str(e)}"
        sys.stderr.write(f"错误: {error_msg}\n")

        # 如果是连接相关错误，抛出 ConnectionError
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            raise ConnectionError(error_msg) from e
        else:
            raise Exception(error_msg) from e

    return client


def create_gitee_mcp_client():
    """
    创建连接至 Gitee MCP 服务的客户端。

    该函数会从环境变量或配置文件中读取 GITEE_TOKEN，并使用该密钥
    创建并返回 MultiServerMCPClient 实例。配置优先级：环境变量 > config.json。

    MCP Server: https://api.gitee.com/mcp
    认证方式: Bearer Token (GITEE_TOKEN)

    Returns:
        MultiServerMCPClient: GITEE MCP 客户端实例

    Raises:
        ImportError: 当无法导入 MultiServerMCPClient 时抛出
        ValueError: 当 GITEE_TOKEN 未配置或为空时抛出
        ConnectionError: 当无法连接到 MCP 服务器时抛出
        Exception: 当创建客户端时发生其他错误时抛出

    功能说明:
        - 首先尝试从环境变量 GITEE_TOKEN 读取 API 密钥
        - 如果环境变量不存在，则从项目根目录下的 config.json 文件中读取
        - 如果两种方式都未找到密钥，抛出 ValueError 异常
        - 使用获取的 API 密钥创建 MultiServerMCPClient 实例
        - 配置 Bearer Token 认证头
        - 处理各种可能的错误情况（密钥缺失、配置文件读取失败、连接失败等）

    示例:
        >>> client = create_gitee_mcp_client()
        >>> tools = await client.get_tools()
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as e:
        error_msg = (
            f"无法导入 MultiServerMCPClient: {str(e)}. "
            "请确保已安装 langchain_mcp_adapters 库。"
        )
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ImportError(error_msg) from e

    api_key = None
    config_error = None

    # 首先尝试从环境变量获取 API 密钥
    api_key = os.getenv("GITEE_TOKEN")

    # 如果环境变量中没有，从 config.json 读取
    if not api_key:
        try:
            config_path = Path(__file__).parent.parent / "config.json"

            if not config_path.exists():
                config_error = f"配置文件不存在: {config_path}"
            else:
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        api_key = config.get("GITEE_TOKEN")

                        if api_key and not isinstance(api_key, str):
                            config_error = (
                                "GITEE_TOKEN 在配置文件中必须是字符串类型"
                            )
                            api_key = None
                except json.JSONDecodeError as e:
                    config_error = f"配置文件格式错误: {str(e)}"
                except IOError as e:
                    config_error = f"读取配置文件失败: {str(e)}"
        except Exception as e:
            config_error = f"处理配置文件时发生错误: {str(e)}"

    # 验证 API 密钥
    if not api_key:
        error_msg = (
            "GITEE_TOKEN 未设置。请设置环境变量 GITEE_TOKEN "
            "或在 config.json 中配置 GITEE_TOKEN"
        )
        if config_error:
            error_msg += f" 配置文件错误: {config_error}"
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ValueError(error_msg)

    # 去除 API 密钥首尾空白
    api_key = api_key.strip()

    if not api_key:
        error_msg = "GITEE_TOKEN 不能为空"
        sys.stderr.write(f"错误: {error_msg}\n")
        raise ValueError(error_msg)

    # 创建 MultiServerMCPClient 实例（使用 HTTP 传输）
    try:
        client = MultiServerMCPClient(
            {
                "context7": {
                    "url": "https://api.gitee.com/mcp",
                    "transport": "streamable_http",
                    "headers": {"Authorization": f"Bearer {api_key}"},
                }
            }
        )
    except Exception as e:
        error_msg = f"创建 Gitee MCP 客户端失败: {str(e)}"
        sys.stderr.write(f"错误: {error_msg}\n")

        # 如果是连接相关错误，抛出 ConnectionError
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            raise ConnectionError(error_msg) from e
        else:
            raise Exception(error_msg) from e

    return client


def get_mcp_clients():
    """
    初始化 LangChain 和 Context7 的 MCP 客户端

    Returns:
        tuple: (langchain_mcp_client, context7_mcp_client)
    """
    langchain_mcp_client = create_langchain_mcp_client()
    context7_mcp_client = create_context7_mcp_client()

    return langchain_mcp_client, context7_mcp_client
