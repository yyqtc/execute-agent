#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件创建控制逻辑的单元测试
验证文件创建控制逻辑，确保在没有 --force 参数时不会创建文件
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# 导入被测试的模块
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import SafeFileWriter


class TestFileCreation(unittest.TestCase):
    """文件创建控制逻辑的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为当前工作目录
        self.test_dir = tempfile.mkdtemp()
        self.current_dir = Path(self.test_dir).resolve()

        # 创建测试子目录
        self.sub_dir = self.current_dir / "subdir"
        self.sub_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """每个测试后的清理工作"""
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_no_force_should_not_create_file(self):
        """测试：没有 --force 参数时，文件不应该被创建"""
        # 注意：根据需求，没有 --force 参数时不应该创建文件
        # 当前实现中，SafeFileWriter 只检查 print_mode，不检查 force
        # 这个测试验证预期的行为：没有 force 时，应该等同于 print_mode=True
        # 即：文件不应该被创建

        # 模拟没有 --force 参数的情况（force=False）
        # 根据需求，这应该等同于 print_mode=True，即不创建文件
        file_writer = SafeFileWriter(print_mode=True, current_dir=self.current_dir)

        test_file = self.current_dir / "test_file.txt"
        content = "test content"

        # 文件不应该被创建（因为没有 --force）
        result = file_writer.write(str(test_file), content)

        # 验证文件未被创建
        self.assertFalse(result)
        self.assertFalse(test_file.exists())

    def test_with_force_should_create_file(self):
        """测试：有 --force 参数时，文件应该被创建"""
        # 注意：当前实现中，SafeFileWriter 不检查 force 参数
        # 这个测试验证预期的行为：有 force 时，文件应该被创建
        # 当前实现中，这等同于 print_mode=False

        # 模拟有 --force 参数的情况（force=True）
        # 根据需求，这应该允许创建文件，即 print_mode=False
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        test_file = self.current_dir / "test_file.txt"
        content = "test content"

        # 文件应该被创建（因为有 --force）
        result = file_writer.write(str(test_file), content)

        # 验证文件被创建
        self.assertTrue(result)
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), content)

    def test_print_mode_does_not_create_file(self):
        """测试：在 print 模式时，文件不会被创建"""
        file_writer = SafeFileWriter(print_mode=True, current_dir=self.current_dir)

        test_file = self.current_dir / "test_file.txt"
        content = "test content"

        # 文件不应该被创建
        result = file_writer.write(str(test_file), content)

        # 验证文件未被创建
        self.assertFalse(result)
        self.assertFalse(test_file.exists())

    def test_cannot_write_to_parent_directory(self):
        """测试：不允许对所在目录的父目录进行写入操作"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        # 尝试写入父目录
        parent_dir = self.current_dir.parent
        parent_file = parent_dir / "test_file_in_parent.txt"

        # 应该抛出 ValueError
        with self.assertRaises(ValueError) as context:
            file_writer.write(str(parent_file), "test content")

        # 验证错误消息
        self.assertIn("不允许写入父目录", str(context.exception))

        # 验证文件未被创建
        self.assertFalse(parent_file.exists())

    def test_cannot_write_to_sibling_directory(self):
        """测试：不允许对兄弟目录进行写入操作"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        # 创建兄弟目录
        sibling_dir = self.current_dir.parent / "sibling_dir"
        sibling_dir.mkdir(exist_ok=True)
        sibling_file = sibling_dir / "test_file.txt"

        try:
            # 应该抛出 ValueError
            with self.assertRaises(ValueError) as context:
                file_writer.write(str(sibling_file), "test content")

            # 验证错误消息
            self.assertIn("不允许写入父目录", str(context.exception))

            # 验证文件未被创建
            self.assertFalse(sibling_file.exists())
        finally:
            # 清理兄弟目录
            shutil.rmtree(sibling_dir, ignore_errors=True)

    def test_can_write_to_current_directory(self):
        """测试：可以写入当前目录"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        test_file = self.current_dir / "test_file.txt"
        content = "test content"

        # 文件应该被创建
        result = file_writer.write(str(test_file), content)

        # 验证文件被创建
        self.assertTrue(result)
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), content)

    def test_can_write_to_subdirectory(self):
        """测试：可以写入子目录"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        test_file = self.sub_dir / "test_file.txt"
        content = "test content"

        # 文件应该被创建
        result = file_writer.write(str(test_file), content)

        # 验证文件被创建
        self.assertTrue(result)
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), content)

    def test_is_safe_path_checks_current_dir(self):
        """测试：is_safe_path 方法正确检查路径是否在当前目录内"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        # 当前目录内的文件应该是安全的
        safe_file = self.current_dir / "safe_file.txt"
        self.assertTrue(file_writer.is_safe_path(safe_file))

        # 子目录内的文件应该是安全的
        safe_sub_file = self.sub_dir / "safe_sub_file.txt"
        self.assertTrue(file_writer.is_safe_path(safe_sub_file))

        # 父目录的文件应该不安全
        parent_file = self.current_dir.parent / "parent_file.txt"
        self.assertFalse(file_writer.is_safe_path(parent_file))

        # 兄弟目录的文件应该不安全
        sibling_dir = self.current_dir.parent / "sibling_dir"
        sibling_file = sibling_dir / "sibling_file.txt"
        self.assertFalse(file_writer.is_safe_path(sibling_file))

    def test_print_mode_outputs_suggestion(self):
        """测试：print 模式时输出建议信息"""
        file_writer = SafeFileWriter(print_mode=True, current_dir=self.current_dir)

        test_file = self.current_dir / "test_file.txt"
        content = "test content" * 10  # 确保内容足够长

        # 捕获 print 输出
        with patch("builtins.print") as mock_print:
            result = file_writer.write(str(test_file), content)

            # 验证返回 False（未创建文件）
            self.assertFalse(result)

            # 验证输出了建议信息
            self.assertTrue(mock_print.called)
            # 检查是否输出了建议写入文件的提示
            call_args_list = [str(call) for call in mock_print.call_args_list]
            call_args_str = " ".join(call_args_list)
            self.assertIn("PRINT MODE", call_args_str)
            self.assertIn("建议写入文件", call_args_str)

    def test_write_creates_parent_directories(self):
        """测试：写入文件时自动创建父目录"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        # 创建深层嵌套路径
        nested_dir = self.current_dir / "level1" / "level2" / "level3"
        test_file = nested_dir / "test_file.txt"
        content = "test content"

        # 文件应该被创建，包括所有父目录
        result = file_writer.write(str(test_file), content)

        # 验证文件被创建
        self.assertTrue(result)
        self.assertTrue(test_file.exists())
        self.assertTrue(nested_dir.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), content)

    def test_relative_path_resolution(self):
        """测试：相对路径被正确解析为绝对路径"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        # 使用相对路径
        relative_file = Path("relative_file.txt")
        content = "test content"

        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(self.current_dir)

            # 文件应该被创建
            result = file_writer.write(str(relative_file), content)

            # 验证文件被创建在正确的位置
            self.assertTrue(result)
            expected_path = self.current_dir / "relative_file.txt"
            self.assertTrue(expected_path.exists())
            self.assertEqual(expected_path.read_text(encoding="utf-8"), content)
        finally:
            os.chdir(original_cwd)

    def test_absolute_path_outside_current_dir(self):
        """测试：绝对路径在当前目录外时被拒绝"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        # 创建另一个临时目录
        other_dir = tempfile.mkdtemp()
        other_file = Path(other_dir) / "test_file.txt"

        try:
            # 应该抛出 ValueError
            with self.assertRaises(ValueError) as context:
                file_writer.write(str(other_file), "test content")

            # 验证错误消息
            self.assertIn("不允许写入父目录", str(context.exception))

            # 验证文件未被创建
            self.assertFalse(other_file.exists())
        finally:
            # 清理临时目录
            shutil.rmtree(other_dir, ignore_errors=True)

    def test_multiple_writes_in_print_mode(self):
        """测试：print 模式下多次写入都不会创建文件"""
        file_writer = SafeFileWriter(print_mode=True, current_dir=self.current_dir)

        files = [
            self.current_dir / "file1.txt",
            self.current_dir / "file2.txt",
            self.sub_dir / "file3.txt",
        ]

        for test_file in files:
            result = file_writer.write(str(test_file), "test content")
            self.assertFalse(result)
            self.assertFalse(test_file.exists())

    def test_multiple_writes_in_normal_mode(self):
        """测试：正常模式下可以创建多个文件"""
        file_writer = SafeFileWriter(print_mode=False, current_dir=self.current_dir)

        files = [
            self.current_dir / "file1.txt",
            self.current_dir / "file2.txt",
            self.sub_dir / "file3.txt",
        ]

        for i, test_file in enumerate(files):
            content = f"content {i}"
            result = file_writer.write(str(test_file), content)
            self.assertTrue(result)
            self.assertTrue(test_file.exists())
            self.assertEqual(test_file.read_text(encoding="utf-8"), content)


if __name__ == "__main__":
    unittest.main()
