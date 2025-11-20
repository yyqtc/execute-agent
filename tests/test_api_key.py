#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 密钥配置逻辑的单元测试
验证 API 密钥配置逻辑，确保不使用 CURSOR_API_KEY 并且 LLM_API_KEY 为空字符串时提示用户配置
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# 导入被测试的模块
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import _get_config


class TestAPIKeyConfiguration(unittest.TestCase):
    """API 密钥配置逻辑的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 保存原始的环境变量
        self.original_llm_api_key = os.environ.get("LLM_API_KEY")
        self.original_cursor_api_key = os.environ.get("CURSOR_API_KEY")
        self.original_llm_api_base = os.environ.get("LLM_API_BASE")

        # 清除环境变量，确保测试环境干净
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]
        if "CURSOR_API_KEY" in os.environ:
            del os.environ["CURSOR_API_KEY"]
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]

        # 创建临时目录用于存放测试用的 config.json
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复原始环境变量
        if self.original_llm_api_key is not None:
            os.environ["LLM_API_KEY"] = self.original_llm_api_key
        elif "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

        if self.original_cursor_api_key is not None:
            os.environ["CURSOR_API_KEY"] = self.original_cursor_api_key
        elif "CURSOR_API_KEY" in os.environ:
            del os.environ["CURSOR_API_KEY"]

        if self.original_llm_api_base is not None:
            os.environ["LLM_API_BASE"] = self.original_llm_api_base
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
    def test_cursor_api_key_not_used_when_set(self, mock_dirname):
        """测试：即使设置了 CURSOR_API_KEY，也不应该使用它"""
        # 设置 CURSOR_API_KEY 环境变量
        os.environ["CURSOR_API_KEY"] = "cursor-api-key-123"

        # 确保 LLM_API_KEY 未设置
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

        # 创建配置文件，LLM_API_KEY 为空字符串
        config_path = self._create_test_config(
            api_key="", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError，因为 LLM_API_KEY 未设置
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息包含 LLM_API_KEY（而不是 CURSOR_API_KEY）
        error_message = str(context.exception)
        self.assertIn("LLM_API_KEY", error_message)
        self.assertNotIn("CURSOR_API_KEY", error_message)

        # 验证 CURSOR_API_KEY 虽然设置了，但没有被使用
        # 如果代码尝试使用 CURSOR_API_KEY，这里应该会成功，但实际上应该失败
        self.assertIn("未设置", error_message)

    @patch("agent.os.path.dirname")
    def test_empty_llm_api_key_raises_error(self, mock_dirname):
        """测试：LLM_API_KEY 为空字符串时，应该提示用户配置"""
        # 设置 LLM_API_KEY 为空字符串
        os.environ["LLM_API_KEY"] = ""

        # 创建配置文件，LLM_API_KEY 也为空字符串
        config_path = self._create_test_config(
            api_key="", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息提示用户配置 LLM_API_KEY
        error_message = str(context.exception)
        self.assertIn("LLM_API_KEY", error_message)
        self.assertIn("未设置", error_message)
        self.assertIn("请设置", error_message)

    @patch("agent.os.path.dirname")
    def test_empty_llm_api_key_in_config_only(self, mock_dirname):
        """测试：仅在配置文件中 LLM_API_KEY 为空字符串时，应该提示用户配置"""
        # 确保环境变量未设置
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

        # 创建配置文件，LLM_API_KEY 为空字符串
        config_path = self._create_test_config(
            api_key="", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息提示用户配置 LLM_API_KEY
        error_message = str(context.exception)
        self.assertIn("LLM_API_KEY", error_message)
        self.assertIn("未设置", error_message)

    @patch("agent.os.path.dirname")
    def test_empty_llm_api_key_env_var_falls_back_to_config(self, mock_dirname):
        """测试：环境变量 LLM_API_KEY 为空字符串时，回退到配置文件"""
        # 设置环境变量为空字符串
        os.environ["LLM_API_KEY"] = ""

        # 创建配置文件，包含有效的 API key
        config_path = self._create_test_config(
            api_key="valid-config-api-key-123",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该成功，使用配置文件中的值
        config = _get_config()

        # 验证使用了配置文件中的 API key
        self.assertEqual(config["LLM_API_KEY"], "valid-config-api-key-123")

    @patch("agent.os.path.dirname")
    def test_empty_llm_api_key_both_empty_raises_error(self, mock_dirname):
        """测试：环境变量和配置文件中的 LLM_API_KEY 都为空字符串时，应该提示用户配置"""
        # 设置环境变量为空字符串
        os.environ["LLM_API_KEY"] = ""

        # 创建配置文件，LLM_API_KEY 也为空字符串
        config_path = self._create_test_config(
            api_key="", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息提示用户配置 LLM_API_KEY
        error_message = str(context.exception)
        self.assertIn("LLM_API_KEY", error_message)
        self.assertIn("未设置", error_message)
        self.assertIn("请设置", error_message)

    @patch("agent.os.path.dirname")
    def test_cursor_api_key_ignored_even_when_llm_missing(self, mock_dirname):
        """测试：即使 CURSOR_API_KEY 设置了有效值，而 LLM_API_KEY 未设置，也不应该使用 CURSOR_API_KEY"""
        # 设置 CURSOR_API_KEY 环境变量
        os.environ["CURSOR_API_KEY"] = "valid-cursor-api-key-456"

        # 确保 LLM_API_KEY 未设置
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

        # 创建配置文件，不包含 LLM_API_KEY（或为空）
        config_path = self._create_test_config(
            api_key="", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError，因为 LLM_API_KEY 未设置
        # 即使 CURSOR_API_KEY 设置了，也不应该使用它
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息只提到 LLM_API_KEY，不提到 CURSOR_API_KEY
        error_message = str(context.exception)
        self.assertIn("LLM_API_KEY", error_message)
        self.assertNotIn("CURSOR_API_KEY", error_message)

    @patch("agent.os.path.dirname")
    def test_valid_llm_api_key_works(self, mock_dirname):
        """测试：有效的 LLM_API_KEY 应该正常工作"""
        # 设置有效的 LLM_API_KEY 环境变量
        os.environ["LLM_API_KEY"] = "valid-llm-api-key-789"

        # 创建配置文件（即使为空也不影响，因为环境变量优先）
        config_path = self._create_test_config(
            api_key="", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        mock_dirname.return_value = self.test_dir

        # 读取配置应该成功
        config = _get_config()

        # 验证使用了环境变量中的 API key
        self.assertEqual(config["LLM_API_KEY"], "valid-llm-api-key-789")

    @patch("agent.os.path.dirname")
    def test_cursor_api_key_not_in_config_file(self, mock_dirname):
        """测试：即使配置文件中包含 CURSOR_API_KEY，也不应该使用它"""
        # 确保环境变量未设置
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]
        if "CURSOR_API_KEY" in os.environ:
            del os.environ["CURSOR_API_KEY"]

        # 创建配置文件，包含 CURSOR_API_KEY 但不包含 LLM_API_KEY
        config_path = os.path.join(self.test_dir, "config.json")
        config_data = {
            "CURSOR_API_KEY": "cursor-api-key-in-config",
            "LLM_API_KEY": "",
            "LLM_API_BASE": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        mock_dirname.return_value = self.test_dir

        # 读取配置应该抛出 ValueError，因为 LLM_API_KEY 未设置
        # 即使配置文件中包含 CURSOR_API_KEY，也不应该使用它
        with self.assertRaises(ValueError) as context:
            _get_config()

        # 验证错误消息只提到 LLM_API_KEY
        error_message = str(context.exception)
        self.assertIn("LLM_API_KEY", error_message)
        self.assertNotIn("CURSOR_API_KEY", error_message)


if __name__ == "__main__":
    unittest.main()
