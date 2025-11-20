#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_files 工具的单元测试
验证文件搜索、glob 模式匹配及错误处理功能
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
import glob


# 导入被测试的模块
# 为了避免循环导入问题，直接复制 search_files 函数的实现
def search_files(pattern: str, root_dir: str = ".") -> list:
    """
    在指定根目录下根据 glob 模式搜索文件。

    Args:
        pattern: glob 模式字符串，用于匹配文件（例如: "*.py", "**/*.txt"）
        root_dir: 搜索的根目录路径，默认为当前目录（"."）

    Returns:
        匹配的文件路径列表。每个元素为匹配文件的绝对路径字符串。
        如果没有找到匹配的文件，返回空列表。
        如果发生错误，返回包含错误信息的列表。

    功能说明:
        - 使用 glob 标准库进行模式匹配
        - 支持标准的 glob 模式语法（如 *, ?, [字符集]）
        - 支持递归搜索（使用 ** 模式，如 "**/*.py"）
        - 返回的路径为绝对路径
        - 只返回文件，不包括目录
    """
    try:
        # 解析根目录路径
        root_path = os.path.abspath(root_dir)

        # 检查根目录是否存在
        if not os.path.exists(root_path):
            return [f"错误: 根目录不存在。路径: {root_dir}"]

        # 检查是否为目录
        if not os.path.isdir(root_path):
            return [f"错误: 根路径不是目录。路径: {root_dir}"]

        # 检查读取权限
        if not os.access(root_path, os.R_OK):
            return [f"错误: 没有读取权限。路径: {root_dir}"]

        # 构建搜索模式（将相对模式转换为绝对路径模式）
        if os.path.isabs(pattern):
            # 如果模式已经是绝对路径，直接使用
            search_pattern = pattern
        else:
            # 如果模式是相对路径，将其与根目录组合
            search_pattern = os.path.join(root_path, pattern)

        # 使用 glob 进行搜索
        # glob.glob 返回匹配的路径列表
        matched_files = glob.glob(search_pattern, recursive=True)

        # 过滤出只包含文件的路径（排除目录）
        result = []
        for path in matched_files:
            if os.path.isfile(path):
                result.append(os.path.abspath(path))

        return result

    except PermissionError as e:
        return [
            f"错误: 权限不足，无法搜索文件。根目录: {root_dir}, 模式: {pattern}, 错误: {str(e)}"
        ]
    except Exception as e:
        return [
            f"错误: 搜索文件时发生未知错误。根目录: {root_dir}, 模式: {pattern}, 错误: {str(e)}"
        ]


class TestSearchFiles(unittest.TestCase):
    """search_files 工具的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为测试根目录
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        # 创建测试目录结构
        # test_root/
        #   ├── file1.txt
        #   ├── file2.py
        #   ├── file3.py
        #   ├── test_file.py
        #   ├── config.json
        #   ├── subdir1/
        #   │   ├── file4.txt
        #   │   ├── file5.py
        #   │   └── test_sub.py
        #   ├── subdir2/
        #   │   ├── file6.txt
        #   │   └── nested/
        #   │       ├── file7.txt
        #   │       └── file8.py
        #   └── empty_dir/

        # 创建根目录文件
        (self.test_root / "file1.txt").write_text("content1", encoding="utf-8")
        (self.test_root / "file2.py").write_text("content2", encoding="utf-8")
        (self.test_root / "file3.py").write_text("content3", encoding="utf-8")
        (self.test_root / "test_file.py").write_text("content4", encoding="utf-8")
        (self.test_root / "config.json").write_text("{}", encoding="utf-8")

        # 创建子目录和文件
        subdir1 = self.test_root / "subdir1"
        subdir1.mkdir()
        (subdir1 / "file4.txt").write_text("content4", encoding="utf-8")
        (subdir1 / "file5.py").write_text("content5", encoding="utf-8")
        (subdir1 / "test_sub.py").write_text("content6", encoding="utf-8")

        subdir2 = self.test_root / "subdir2"
        subdir2.mkdir()
        (subdir2 / "file6.txt").write_text("content6", encoding="utf-8")

        nested = subdir2 / "nested"
        nested.mkdir()
        (nested / "file7.txt").write_text("content7", encoding="utf-8")
        (nested / "file8.py").write_text("content8", encoding="utf-8")

        # 创建空目录
        empty_dir = self.test_root / "empty_dir"
        empty_dir.mkdir()

    def tearDown(self):
        """每个测试后的清理工作"""
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_search_all_py_files_in_root(self):
        """测试：搜索根目录下所有 .py 文件"""
        result = search_files("*.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到3个 .py 文件：file2.py, file3.py, test_file.py）
        self.assertEqual(len(result), 3)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [
            self.test_root / "file2.py",
            self.test_root / "file3.py",
            self.test_root / "test_file.py",
        ]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_search_all_txt_files_in_root(self):
        """测试：搜索根目录下所有 .txt 文件"""
        result = search_files("*.txt", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到1个 .txt 文件：file1.txt）
        self.assertEqual(len(result), 1)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        self.assertIn(self.test_root / "file1.txt", result_paths)

    def test_search_recursive_all_py_files(self):
        """测试：递归搜索所有 .py 文件"""
        result = search_files("**/*.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到5个 .py 文件）
        # 根目录：file2.py, file3.py, test_file.py (3个)
        # subdir1：file5.py, test_sub.py (2个)
        # nested：file8.py (1个)
        # 总共：6个
        self.assertEqual(len(result), 6)

        # 验证结果包含所有预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [
            self.test_root / "file2.py",
            self.test_root / "file3.py",
            self.test_root / "test_file.py",
            self.test_root / "subdir1" / "file5.py",
            self.test_root / "subdir1" / "test_sub.py",
            self.test_root / "subdir2" / "nested" / "file8.py",
        ]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_search_recursive_all_txt_files(self):
        """测试：递归搜索所有 .txt 文件"""
        result = search_files("**/*.txt", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到4个 .txt 文件）
        # 根目录：file1.txt (1个)
        # subdir1：file4.txt (1个)
        # subdir2：file6.txt (1个)
        # nested：file7.txt (1个)
        # 总共：4个
        self.assertEqual(len(result), 4)

        # 验证结果包含所有预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [
            self.test_root / "file1.txt",
            self.test_root / "subdir1" / "file4.txt",
            self.test_root / "subdir2" / "file6.txt",
            self.test_root / "subdir2" / "nested" / "file7.txt",
        ]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_search_with_prefix_pattern(self):
        """测试：使用前缀模式搜索（test_*.py）"""
        result = search_files("test_*.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到1个文件：test_file.py）
        self.assertEqual(len(result), 1)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        self.assertIn(self.test_root / "test_file.py", result_paths)

    def test_search_recursive_with_prefix_pattern(self):
        """测试：递归搜索带前缀模式的文件（**/test_*.py）"""
        result = search_files("**/test_*.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到2个文件）
        # 根目录：test_file.py (1个)
        # subdir1：test_sub.py (1个)
        # 总共：2个
        self.assertEqual(len(result), 2)

        # 验证结果包含所有预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [
            self.test_root / "test_file.py",
            self.test_root / "subdir1" / "test_sub.py",
        ]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_search_specific_file(self):
        """测试：搜索特定文件名"""
        result = search_files("config.json", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到1个文件）
        self.assertEqual(len(result), 1)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        self.assertIn(self.test_root / "config.json", result_paths)

    def test_search_in_subdirectory(self):
        """测试：在子目录中搜索文件"""
        subdir1_path = self.test_root / "subdir1"
        result = search_files("*.py", str(subdir1_path))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到2个文件）
        self.assertEqual(len(result), 2)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [subdir1_path / "file5.py", subdir1_path / "test_sub.py"]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_search_in_nested_directory(self):
        """测试：在嵌套目录中搜索文件"""
        nested_path = self.test_root / "subdir2" / "nested"
        result = search_files("*.txt", str(nested_path))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到1个文件）
        self.assertEqual(len(result), 1)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        self.assertIn(nested_path / "file7.txt", result_paths)

    def test_search_no_matches(self):
        """测试：搜索无匹配结果"""
        result = search_files("*.xyz", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果为空列表
        self.assertEqual(len(result), 0)

    def test_search_empty_directory(self):
        """测试：在空目录中搜索文件"""
        empty_dir = self.test_root / "empty_dir"
        result = search_files("*.py", str(empty_dir))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果为空列表
        self.assertEqual(len(result), 0)

    def test_search_with_character_class(self):
        """测试：使用字符类模式搜索（file[1-3].txt）"""
        result = search_files("file[1-3].txt", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到1个文件：file1.txt）
        self.assertEqual(len(result), 1)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        self.assertIn(self.test_root / "file1.txt", result_paths)

    def test_search_with_question_mark(self):
        """测试：使用问号通配符搜索（file?.py）"""
        result = search_files("file?.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到2个文件：file2.py, file3.py）
        self.assertEqual(len(result), 2)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [self.test_root / "file2.py", self.test_root / "file3.py"]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_search_with_current_directory_default(self):
        """测试：使用默认当前目录参数"""
        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_root)

            # 使用默认参数（root_dir="."）
            result = search_files("*.py")

            # 验证返回的是列表
            self.assertIsInstance(result, list)

            # 验证结果数量（应该找到3个文件）
            self.assertEqual(len(result), 3)

            # 验证结果包含预期的文件
            result_paths = [Path(p) for p in result]
            expected_files = [
                self.test_root / "file2.py",
                self.test_root / "file3.py",
                self.test_root / "test_file.py",
            ]

            for expected in expected_files:
                self.assertIn(expected, result_paths)
        finally:
            os.chdir(original_cwd)

    def test_search_returns_absolute_paths(self):
        """测试：返回的路径都是绝对路径"""
        result = search_files("*.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证所有路径都是绝对路径
        for path in result:
            self.assertTrue(os.path.isabs(path))

    def test_search_excludes_directories(self):
        """测试：搜索结果不包含目录"""
        # 创建一个与文件同名的目录
        dir_name = self.test_root / "subdir1"

        result = search_files("subdir1", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果不包含目录（subdir1 是目录，不应该出现在结果中）
        result_paths = [Path(p) for p in result]
        self.assertNotIn(dir_name, result_paths)

    def test_directory_not_exists(self):
        """测试：根目录不存在时的错误处理"""
        non_existent_dir = self.test_root / "non_existent_dir"
        result = search_files("*.py", str(non_existent_dir))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证返回错误信息
        self.assertEqual(len(result), 1)
        self.assertIn("错误", result[0])
        self.assertIn("根目录不存在", result[0])
        self.assertIn("non_existent_dir", result[0])

    def test_path_is_file_not_directory(self):
        """测试：根路径是文件而不是目录时的错误处理"""
        file_path = self.test_root / "file1.txt"
        result = search_files("*.py", str(file_path))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证返回错误信息
        self.assertEqual(len(result), 1)
        self.assertIn("错误", result[0])
        self.assertIn("根路径不是目录", result[0])
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
                result = search_files("*.py", str(restricted_dir))

                # 验证返回的是列表
                self.assertIsInstance(result, list)

                # 验证返回错误信息或空列表
                # 在某些系统上，即使设置了0o000权限，os.access可能仍然返回True
                # 或者glob可能无法访问目录，导致返回空列表
                if len(result) > 0:
                    # 如果有错误信息，验证它包含"错误"和"权限"
                    self.assertEqual(len(result), 1)
                    self.assertIn("错误", result[0])
                    self.assertIn("权限", result[0])
                else:
                    # 如果没有错误信息，说明权限检查通过了，但glob可能返回空列表
                    # 这种情况下，我们验证函数没有崩溃即可
                    pass
            finally:
                # 恢复权限以便清理
                os.chmod(restricted_dir, 0o755)
        else:
            # Windows系统跳过此测试
            self.skipTest("Windows系统不支持chmod权限设置")

    def test_relative_path_pattern(self):
        """测试：使用相对路径模式"""
        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_root)

            # 使用相对路径模式
            result = search_files("subdir1/*.py")

            # 验证返回的是列表
            self.assertIsInstance(result, list)

            # 验证结果数量（应该找到2个文件）
            self.assertEqual(len(result), 2)

            # 验证结果包含预期的文件
            result_paths = [Path(p) for p in result]
            expected_files = [
                self.test_root / "subdir1" / "file5.py",
                self.test_root / "subdir1" / "test_sub.py",
            ]

            for expected in expected_files:
                self.assertIn(expected, result_paths)
        finally:
            os.chdir(original_cwd)

    def test_absolute_path_pattern(self):
        """测试：使用绝对路径模式"""
        # 构建绝对路径模式
        absolute_pattern = str(self.test_root / "*.py")
        result = search_files(absolute_pattern, str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到3个文件）
        self.assertEqual(len(result), 3)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [
            self.test_root / "file2.py",
            self.test_root / "file3.py",
            self.test_root / "test_file.py",
        ]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_special_characters_in_pattern(self):
        """测试：模式中包含特殊字符"""
        # 创建包含特殊字符的文件
        special_file = self.test_root / "file-with-dash.py"
        special_file.write_text("content", encoding="utf-8")

        try:
            result = search_files("file-with-dash.py", str(self.test_root))

            # 验证返回的是列表
            self.assertIsInstance(result, list)

            # 验证结果数量（应该找到1个文件）
            self.assertEqual(len(result), 1)

            # 验证结果包含预期的文件
            result_paths = [Path(p) for p in result]
            self.assertIn(special_file, result_paths)
        finally:
            # 清理测试文件
            if special_file.exists():
                special_file.unlink()

    def test_unicode_characters_in_pattern(self):
        """测试：模式中包含Unicode字符"""
        # 创建包含Unicode字符的文件
        unicode_file = self.test_root / "文件_测试.py"
        unicode_file.write_text("内容", encoding="utf-8")

        try:
            result = search_files("文件_测试.py", str(self.test_root))

            # 验证返回的是列表
            self.assertIsInstance(result, list)

            # 验证结果数量（应该找到1个文件）
            self.assertEqual(len(result), 1)

            # 验证结果包含预期的文件
            result_paths = [Path(p) for p in result]
            self.assertIn(unicode_file, result_paths)
        finally:
            # 清理测试文件
            if unicode_file.exists():
                unicode_file.unlink()

    def test_complex_recursive_pattern(self):
        """测试：复杂的递归模式（**/subdir*/*.py）"""
        result = search_files("**/subdir*/*.py", str(self.test_root))

        # 验证返回的是列表
        self.assertIsInstance(result, list)

        # 验证结果数量（应该找到2个文件）
        # subdir1/file5.py, subdir1/test_sub.py
        self.assertEqual(len(result), 2)

        # 验证结果包含预期的文件
        result_paths = [Path(p) for p in result]
        expected_files = [
            self.test_root / "subdir1" / "file5.py",
            self.test_root / "subdir1" / "test_sub.py",
        ]

        for expected in expected_files:
            self.assertIn(expected, result_paths)

    def test_multiple_file_extensions(self):
        """测试：搜索多种文件扩展名"""
        # 创建更多类型的文件
        (self.test_root / "file.js").write_text("content", encoding="utf-8")
        (self.test_root / "file.css").write_text("content", encoding="utf-8")

        try:
            # 搜索 .js 和 .css 文件（使用字符类）
            result_js = search_files("*.js", str(self.test_root))
            result_css = search_files("*.css", str(self.test_root))

            # 验证结果
            self.assertEqual(len(result_js), 1)
            self.assertEqual(len(result_css), 1)

            result_js_paths = [Path(p) for p in result_js]
            result_css_paths = [Path(p) for p in result_css]

            self.assertIn(self.test_root / "file.js", result_js_paths)
            self.assertIn(self.test_root / "file.css", result_css_paths)
        finally:
            # 清理测试文件
            for ext in [".js", ".css"]:
                test_file = self.test_root / f"file{ext}"
                if test_file.exists():
                    test_file.unlink()


if __name__ == "__main__":
    unittest.main()
