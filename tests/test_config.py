#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置读取逻辑的单元测试
验证 config.json 和环境变量的读取逻辑，确保空字符串处理和环境变量优先级正确
"""

import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open

# 导入被测试的模块
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import _get_config


class TestConfigReading(unittest.TestCase):
    """配置读取逻辑的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 保存原始的环境变量
        self.original_api_key = os.environ.get("LLM_API_KEY")
        self.original_api_base = os.environ.get("LLM_API_BASE")

        # 清除环境变量，确保测试环境干净
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 创建临时目录用于存放测试用的 config.json
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复原始环境变量
        if self.original_api_key is not None:
            os.environ["LLM_API_KEY"] = self.original_api_key
        elif "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

        if self.original_api_base is not None:
            os.environ["LLM_API_BASE"] = self.original_api_base
        elif "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_config(self, api_key="", api_base=""):
        """创建测试用的 config.json 文件"""
        config_path = os.path.join(self.test_dir, "config.json")
        config_data = {"LLM_API_KEY": api_key, "LLM_API_BASE": api_base}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        return config_path

    @patch("agent.os.path.dirname")
    def test_env_var_priority_over_config_file(self, mock_dirname):
        """测试环境变量优先级高于配置文件"""
        # 设置环境变量
        os.environ["LLM_API_KEY"] = "env-api-key-123"
        os.environ["LLM_API_BASE"] = "https://env-api-base.com"

        # 创建包含不同值的配置文件
        config_path = self._create_test_config(
            api_key="config-api-key-456", api_base="https://config-api-base.com"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证环境变量的值被使用
        self.assertEqual(config["LLM_API_KEY"], "env-api-key-123")
        self.assertEqual(config["LLM_API_BASE"], "https://env-api-base.com")

    @patch("agent.os.path.dirname")
    def test_config_file_when_env_var_not_set(self, mock_dirname):
        """测试当环境变量未设置时，从配置文件读取"""
        # 确保环境变量未设置
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 创建配置文件
        config_path = self._create_test_config(
            api_key="config-api-key-789", api_base="https://config-api-base.com"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证配置文件的值被使用
        self.assertEqual(config["LLM_API_KEY"], "config-api-key-789")
        self.assertEqual(config["LLM_API_BASE"], "https://config-api-base.com")

    @patch("agent.os.path.dirname")
    def test_empty_string_env_var_falls_back_to_config(self, mock_dirname):
        """测试环境变量为空字符串时，回退到配置文件"""
        # 设置环境变量为空字符串
        os.environ["LLM_API_KEY"] = ""
        os.environ["LLM_API_BASE"] = ""

        # 创建配置文件
        config_path = self._create_test_config(
            api_key="config-api-key-empty-env",
            api_base="https://config-api-base-empty-env.com",
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证配置文件的值被使用（因为环境变量为空字符串）
        self.assertEqual(config["LLM_API_KEY"], "config-api-key-empty-env")
        self.assertEqual(
            config["LLM_API_BASE"], "https://config-api-base-empty-env.com"
        )

    @patch("agent.os.path.dirname")
    def test_empty_string_config_falls_back_to_default_for_api_base(self, mock_dirname):
        """测试配置文件中 api_base 为空字符串时，使用默认值"""
        # 确保环境变量未设置
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 创建配置文件，api_base 为空字符串
        config_path = self._create_test_config(
            api_key="config-api-key-default", api_base=""
        )
        mock_dirname.return_value = self.test_dir

        # 设置有效的 API key 环境变量
        os.environ["LLM_API_KEY"] = "env-api-key-default"

        # 读取配置
        config = _get_config()

        # 验证 api_base 使用默认值
        self.assertEqual(
            config["LLM_API_BASE"], "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.assertEqual(config["LLM_API_KEY"], "env-api-key-default")

    @patch("agent.os.path.dirname")
    def test_empty_string_both_env_and_config_for_api_base(self, mock_dirname):
        """测试环境变量和配置文件都为空字符串时，api_base 使用默认值"""
        # 设置环境变量为空字符串
        os.environ["LLM_API_BASE"] = ""

        # 创建配置文件，api_base 也为空字符串
        config_path = self._create_test_config(
            api_key="config-api-key-both-empty", api_base=""
        )
        mock_dirname.return_value = self.test_dir

        # 设置有效的 API key
        os.environ["LLM_API_KEY"] = "env-api-key-both-empty"

        # 读取配置
        config = _get_config()

        # 验证 api_base 使用默认值
        self.assertEqual(
            config["LLM_API_BASE"], "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    @patch("agent.os.path.dirname")
    def test_default_api_base_when_not_in_env_and_config(self, mock_dirname):
        """测试当环境变量和配置文件中都没有 api_base 时，使用默认值"""
        # 确保环境变量未设置
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 创建配置文件，不包含 api_base 或值为 None
        config_path = os.path.join(self.test_dir, "config.json")
        config_data = {"LLM_API_KEY": "config-api-key-no-base"}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        mock_dirname.return_value = self.test_dir

        # 设置有效的 API key
        os.environ["LLM_API_KEY"] = "env-api-key-no-base"

        # 读取配置
        config = _get_config()

        # 验证 api_base 使用默认值
        self.assertEqual(
            config["LLM_API_BASE"], "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    @patch("agent.os.path.dirname")
    def test_empty_string_api_key_raises_error(self, mock_dirname):
        """测试当 API key 在环境变量和配置文件中都为空字符串时，抛出错误"""
        # 设置环境变量为空字符串
        os.environ["LLM_API_KEY"] = ""

        # 创建配置文件，api_key 也为空字符串
        config_path = self._create_test_config(
            api_key="", api_base="https://config-api-base.com"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息
        self.assertIn("LLM_API_KEY 未设置", str(context.exception))

    @patch("agent.os.path.dirname")
    def test_missing_config_file_falls_back_to_env_only(self, mock_dirname):
        """测试配置文件不存在时，只使用环境变量"""
        # 设置环境变量
        os.environ["LLM_API_KEY"] = "env-api-key-no-config"
        os.environ["LLM_API_BASE"] = "https://env-api-base-no-config.com"

        # 模拟配置文件不存在（使用不存在的目录）
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证环境变量的值被使用
        self.assertEqual(config["LLM_API_KEY"], "env-api-key-no-config")
        self.assertEqual(config["LLM_API_BASE"], "https://env-api-base-no-config.com")

    @patch("agent.os.path.dirname")
    def test_missing_config_file_with_env_api_key_only(self, mock_dirname):
        """测试配置文件不存在，只有环境变量 API key，api_base 使用默认值"""
        # 只设置 API key 环境变量
        os.environ["LLM_API_KEY"] = "env-api-key-default-base"

        # 确保 api_base 环境变量未设置
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 模拟配置文件不存在
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证 API key 来自环境变量，api_base 使用默认值
        self.assertEqual(config["LLM_API_KEY"], "env-api-key-default-base")
        self.assertEqual(
            config["LLM_API_BASE"], "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    @patch("agent.os.path.dirname")
    def test_partial_env_var_partial_config(self, mock_dirname):
        """测试部分环境变量、部分配置文件的混合场景"""
        # 只设置 API key 环境变量
        os.environ["LLM_API_KEY"] = "env-api-key-partial"

        # 确保 api_base 环境变量未设置
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 创建配置文件，只包含 api_base
        config_path = self._create_test_config(
            api_key="",  # 配置文件中的 api_key 为空，但环境变量有值
            api_base="https://config-api-base-partial.com",
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证 API key 来自环境变量，api_base 来自配置文件
        self.assertEqual(config["LLM_API_KEY"], "env-api-key-partial")
        self.assertEqual(config["LLM_API_BASE"], "https://config-api-base-partial.com")

    @patch("agent.os.path.dirname")
    def test_env_var_empty_config_valid(self, mock_dirname):
        """测试环境变量为空字符串，配置文件有有效值"""
        # 设置环境变量为空字符串
        os.environ["LLM_API_KEY"] = ""
        os.environ["LLM_API_BASE"] = ""

        # 创建配置文件，包含有效值
        config_path = self._create_test_config(
            api_key="valid-config-api-key", api_base="https://valid-config-api-base.com"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证配置文件的值被使用
        self.assertEqual(config["LLM_API_KEY"], "valid-config-api-key")
        self.assertEqual(config["LLM_API_BASE"], "https://valid-config-api-base.com")

    @patch("agent.os.path.dirname")
    def test_env_var_valid_config_empty(self, mock_dirname):
        """测试环境变量有有效值，配置文件为空字符串"""
        # 设置环境变量为有效值
        os.environ["LLM_API_KEY"] = "valid-env-api-key"
        os.environ["LLM_API_BASE"] = "https://valid-env-api-base.com"

        # 创建配置文件，值为空字符串
        config_path = self._create_test_config(api_key="", api_base="")
        mock_dirname.return_value = self.test_dir

        # 读取配置
        config = _get_config()

        # 验证环境变量的值被使用（优先级更高）
        self.assertEqual(config["LLM_API_KEY"], "valid-env-api-key")
        self.assertEqual(config["LLM_API_BASE"], "https://valid-env-api-base.com")


if __name__ == "__main__":
    unittest.main()
