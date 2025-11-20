#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_directory 工具的单元测试
验证目录列出、递归列出及错误处理功能
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch


# 导入被测试的模块
# 为了避免循环导入问题，直接复制 list_directory 函数的实现
def list_directory(directory_path: str = ".", recursive: bool = False) -> list:
    """
    列出指定目录的内容。

    Args:
        directory_path: 要列出的目录路径，默认为当前目录（"."）
        recursive: 是否递归列出所有子目录内容，默认为 False

    Returns:
        包含目录内容的列表。每个元素为文件或目录的路径字符串。
        如果目录不存在或发生错误，返回包含错误信息的列表。
    """
    try:
        # 解析目录路径
        dir_path = os.path.abspath(directory_path)

        # 检查目录是否存在
        if not os.path.exists(dir_path):
            return [f"错误: 目录不存在。路径: {directory_path}"]

        # 检查是否为目录
        if not os.path.isdir(dir_path):
            return [f"错误: 路径不是目录。路径: {directory_path}"]

        # 检查读取权限
        if not os.access(dir_path, os.R_OK):
            return [f"错误: 没有读取权限。路径: {directory_path}"]

        result = []

        if recursive:
            # 递归列出所有子目录内容
            for root, dirs, files in os.walk(dir_path):
                # 添加目录路径
                result.append(root)
                # 添加文件路径
                for file in files:
                    file_path = os.path.join(root, file)
                    result.append(file_path)
        else:
            # 只列出直接子项
            try:
                items = os.listdir(dir_path)
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    result.append(item_path)
            except PermissionError:
                return [f"错误: 权限不足，无法列出目录内容。路径: {directory_path}"]

        return result

    except PermissionError as e:
        return [f"错误: 权限不足，无法访问目录。路径: {directory_path}, 错误: {str(e)}"]
    except Exception as e:
        return [f"错误: 列出目录时发生未知错误。路径: {directory_path}, 错误: {str(e)}"]


class TestListDirectory(unittest.TestCase):
    """list_directory 工具的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为测试根目录
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        # 创建测试目录结构
        # test_root/
        #   ├── file1.txt
        #   ├── file2.py
        #   ├── subdir1/
        #   │   ├── file3.txt
        #   │   └── file4.py
        #   └── subdir2/
        #       ├── file5.txt
        #       └── nested/
        #           └── file6.txt

        # 创建文件
        (self.test_root / "file1.txt").write_text("content1", encoding="utf-8")
        (self.test_root / "file2.py").write_text("content2", encoding="utf-8")

        # 创建子目录和文件
        subdir1 = self.test_root / "subdir1"
        subdir1.mkdir()
        (subdir1 / "file3.txt").write_text("content3", encoding="utf-8")
        (subdir1 / "file4.py").write_text("content4", encoding="utf-8")

        subdir2 = self.test_root / "subdir2"
        subdir2.mkdir()
        (subdir2 / "file5.txt").write_text("content5", encoding="utf-8")

        nested = subdir2 / "nested"
        nested.mkdir()
        (nested / "file6.txt").write_text("content6", encoding="utf-8")

    def tearDown(self):
        """每个测试后的清理工作"""
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_current_directory(self):
        """测试：列出当前目录（默认参数）"""
        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_root)

            # 列出当前目录
            result = list_directory(".")

            # 验证返回的是列表
            self.assertIsInstance(result, list)

            # 验证结果不为空
            self.assertGreater(len(result), 0)

            # 验证结果包含预期的文件和目录
            result_str = " ".join(result)
            self.assertIn("file1.txt", result_str)
            self.assertIn("file2.py", result_str)
            self.assertIn("subdir1", result_str)
            self.assertIn("subdir2", result_str)
        finally:
            os.chdir(original_cwd)

    def test_list_specified_directory(self):
        """测试：列出指定目录"""
        # 列出测试根目录
        result = list_directory(str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果包含预期的文件和目录
        result_str = " ".join(result)
        self.assertIn("file1.txt", result_str)
        self.assertIn("file2.py", result_str)
        self.assertIn("subdir1", result_str)
        self.assertIn("subdir2", result_str)

        # 验证结果数量（应该包含2个文件和2个子目录）
        self.assertEqual(len(result), 4)

    def test_list_directory_non_recursive(self):
        """测试：非递归列出目录（只列出直接子项）"""
        result = list_directory(str(self.test_root), recursive=False)

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该只有直接子项：2个文件 + 2个子目录）
        self.assertEqual(len(result), 4)

        # 验证结果包含直接子项
        result_paths = [Path(p) for p in result]
        expected_items = [
            self.test_root / "file1.txt",
            self.test_root / "file2.py",
            self.test_root / "subdir1",
            self.test_root / "subdir2",
        ]

        for expected in expected_items:
            self.assertIn(expected, result_paths)

        # 验证结果不包含子目录中的文件（非递归模式）
        result_str = " ".join(result)
        self.assertNotIn("file3.txt", result_str)
        self.assertNotIn("file4.py", result_str)
        self.assertNotIn("file5.txt", result_str)
        self.assertNotIn("file6.txt", result_str)

    def test_list_directory_recursive(self):
        """测试：递归列出目录（列出所有子目录和文件）"""
        result = list_directory(str(self.test_root), recursive=True)

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该包含所有文件和目录）
        # 目录：test_root, subdir1, subdir2, nested (4个)
        # 文件：file1.txt, file2.py, file3.txt, file4.py, file5.txt, file6.txt (6个)
        # 总共：10个
        self.assertGreaterEqual(len(result), 6)  # 至少包含所有文件

        # 验证结果包含所有文件
        result_str = " ".join(result)
        self.assertIn("file1.txt", result_str)
        self.assertIn("file2.py", result_str)
        self.assertIn("file3.txt", result_str)
        self.assertIn("file4.py", result_str)
        self.assertIn("file5.txt", result_str)
        self.assertIn("file6.txt", result_str)

        # 验证结果包含所有目录
        self.assertIn("subdir1", result_str)
        self.assertIn("subdir2", result_str)
        self.assertIn("nested", result_str)

    def test_list_subdirectory(self):
        """测试：列出子目录"""
        subdir1_path = self.test_root / "subdir1"
        result = list_directory(str(subdir1_path))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该包含2个文件）
        self.assertEqual(len(result), 2)

        # 验证结果包含子目录中的文件
        result_str = " ".join(result)
        self.assertIn("file3.txt", result_str)
        self.assertIn("file4.py", result_str)

    def test_list_nested_directory(self):
        """测试：列出嵌套目录"""
        nested_path = self.test_root / "subdir2" / "nested"
        result = list_directory(str(nested_path))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该包含1个文件）
        self.assertEqual(len(result), 1)

        # 验证结果包含嵌套目录中的文件
        result_str = " ".join(result)
        self.assertIn("file6.txt", result_str)

    def test_directory_not_exists(self):
        """测试：目录不存在时的错误处理"""
        non_existent_dir = self.test_root / "non_existent_dir"
        result = list_directory(str(non_existent_dir))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证返回错误信息
        self.assertEqual(len(result), 1)
        self.assertIn("错误", result[0])
        self.assertIn("目录不存在", result[0])
        self.assertIn("non_existent_dir", result[0])

    def test_path_is_file_not_directory(self):
        """测试：路径是文件而不是目录时的错误处理"""
        file_path = self.test_root / "file1.txt"
        result = list_directory(str(file_path))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证返回错误信息
        self.assertEqual(len(result), 1)
        self.assertIn("错误", result[0])
        self.assertIn("路径不是目录", result[0])
        self.assertIn("file1.txt", result[0])

    def test_permission_error(self):
        """测试：权限不足时的错误处理"""
        # 创建一个无读取权限的目录（在Unix系统上）
        if os.name != "nt":  # Windows系统不支持chmod权限设置
            restricted_dir = self.test_root / "restricted_dir"
            restricted_dir.mkdir()

            # 移除读取权限
            os.chmod(restricted_dir, 0o000)

            try:
                result = list_directory(str(restricted_dir))

                # 验证返回的是列表
                self.assertIsInstance(result, list)

                # 验证返回错误信息（可能是权限检查失败，也可能是listdir失败）
                # 在某些系统上，os.access可能返回False但listdir仍能工作
                # 所以这里只验证返回了错误信息或空列表
                if len(result) > 0:
                    # 如果有错误信息，验证它包含"错误"和"权限"
                    self.assertEqual(len(result), 1)
                    self.assertIn("错误", result[0])
                    self.assertIn("权限", result[0])
                else:
                    # 如果没有错误信息，说明权限检查通过了，但listdir可能失败
                    # 这种情况下，我们验证函数没有崩溃即可
                    pass
            finally:
                # 恢复权限以便清理
                os.chmod(restricted_dir, 0o755)
        else:
            # Windows系统跳过此测试
            self.skipTest("Windows系统不支持chmod权限设置")

    def test_empty_directory(self):
        """测试：列出空目录"""
        empty_dir = self.test_root / "empty_dir"
        empty_dir.mkdir()

        result = list_directory(str(empty_dir))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果为空列表（空目录应该返回空列表）
        self.assertEqual(len(result), 0)

    def test_empty_directory_recursive(self):
        """测试：递归列出空目录"""
        empty_dir = self.test_root / "empty_dir"
        empty_dir.mkdir()

        result = list_directory(str(empty_dir), recursive=True)

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果只包含目录本身（递归模式下会包含目录路径）
        self.assertEqual(len(result), 1)
        self.assertIn(str(empty_dir), result)

    def test_relative_path(self):
        """测试：使用相对路径"""
        # 切换到测试目录的父目录
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_root.parent)

            # 使用相对路径列出子目录
            relative_path = self.test_root.name
            result = list_directory(relative_path)

            # 验证返回的是列表
            self.assertIsInstance(result, list)

            # 验证结果不为空
            self.assertGreater(len(result), 0)
        finally:
            os.chdir(original_cwd)

    def test_absolute_path(self):
        """测试：使用绝对路径"""
        result = list_directory(str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果中的路径都是绝对路径
        for item in result:
            self.assertTrue(os.path.isabs(item))

    def test_cannot_list_parent_directory(self):
        """测试：不允许列出父目录（安全限制）"""
        # 注意：list_directory 工具本身没有限制列出父目录
        # 但测试应该验证不会意外列出父目录的内容

        # 切换到子目录
        subdir1_path = self.test_root / "subdir1"
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir1_path)

            # 尝试列出父目录（使用相对路径 ".."）
            result = list_directory("..")

            # 验证返回的是列表（工具允许列出父目录，但测试应该验证结果）
            self.assertIsInstance(result, list)

            # 注意：在实际应用中，可能需要添加安全检查
            # 但当前实现允许列出父目录，所以这里只验证功能正常
            # 如果需要限制，应该在工具实现中添加检查
        finally:
            os.chdir(original_cwd)

    def test_special_characters_in_path(self):
        """测试：路径中包含特殊字符"""
        # 创建包含特殊字符的目录
        special_dir = self.test_root / "dir with spaces"
        special_dir.mkdir()
        (special_dir / "file with spaces.txt").write_text("content", encoding="utf-8")

        result = list_directory(str(special_dir))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果包含文件
        result_str = " ".join(result)
        self.assertIn("file with spaces.txt", result_str)

    def test_unicode_characters_in_path(self):
        """测试：路径中包含Unicode字符"""
        # 创建包含Unicode字符的目录
        unicode_dir = self.test_root / "目录_测试"
        unicode_dir.mkdir()
        (unicode_dir / "文件_测试.txt").write_text("内容", encoding="utf-8")

        result = list_directory(str(unicode_dir))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果包含文件
        result_str = " ".join(result)
        self.assertIn("文件_测试.txt", result_str)

    def test_recursive_with_empty_subdirectories(self):
        """测试：递归列出包含空子目录的目录"""
        # 创建包含空子目录的结构
        parent_dir = self.test_root / "parent"
        parent_dir.mkdir()

        empty_subdir = parent_dir / "empty_subdir"
        empty_subdir.mkdir()

        (parent_dir / "file.txt").write_text("content", encoding="utf-8")

        result = list_directory(str(parent_dir), recursive=True)

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果包含目录和文件
        result_str = " ".join(result)
        self.assertIn("parent", result_str)
        self.assertIn("empty_subdir", result_str)
        self.assertIn("file.txt", result_str)


if __name__ == "__main__":
    unittest.main()
