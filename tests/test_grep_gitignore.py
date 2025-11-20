#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grep 函数的 .gitignore 排除功能测试
验证 grep 函数是否正确读取 .gitignore 并排除其中列出的文件和文件夹
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
import sys
import logging
from pathlib import Path

# 抑制除了错误信息和结果信息以外的其他打印信息
logging.basicConfig(level=logging.ERROR)

# 导入 grep 函数
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.search import grep


class TestGrepGitignore(unittest.TestCase):
    """grep 函数的 .gitignore 排除功能测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为测试根目录
        # 注意：grep函数使用get_project_root()获取项目根目录，会返回实际项目根目录
        # 因此测试需要使用实际项目的.gitignore规则
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        # 切换到测试目录（确保路径解析正确）
        self.original_cwd = os.getcwd()
        os.chdir(self.test_root)

        # 注意：实际项目的.gitignore包含以下规则：
        # __pycache__/, data/, docs/, .semantic_cache/, .mypy_cache/, .pytest_cache/, config.json, *.pyc
        # 测试将使用这些规则来验证grep函数的.gitignore功能

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_exclude_single_file(self):
        """测试：排除 .gitignore 中单个文件"""
        # 创建应该被忽略的单个文件（使用实际项目的.gitignore规则：*.pyc）
        (self.test_root / "ignored.pyc").write_text("compiled code\nsearch term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证 .pyc 文件没有被搜索
        for file_path in result:
            self.assertNotIn(".pyc", file_path)
        # 验证 .py 文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_exclude_multiple_files(self):
        """测试：排除 .gitignore 中多个文件"""
        # 创建应该被忽略的多个文件（使用实际项目的.gitignore规则：*.pyc, config.json）
        (self.test_root / "file1.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "file2.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "config.json").write_text('{"key": "search term"}\n', encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")
        (self.test_root / "utils.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证所有被忽略的文件都没有被搜索
        for file_path in result:
            self.assertNotIn(".pyc", file_path)
            self.assertNotIn("config.json", file_path)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result) or any("utils.py" in f for f in result))

    def test_exclude_directory(self):
        """测试：排除 .gitignore 中文件夹"""
        # 创建应该被忽略的目录
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "file1.txt").write_text("search term\n", encoding="utf-8")
        (data_dir / "file2.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证 data 目录中的文件没有被搜索
        for file_path in result:
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_exclude_nested_path(self):
        """测试：排除 .gitignore 中嵌套路径"""
        # 创建嵌套的忽略目录结构
        nested_dir = self.test_root / "src" / "data"
        nested_dir.mkdir(parents=True)
        (nested_dir / "file.txt").write_text("search term\n", encoding="utf-8")
        (nested_dir / "subdir").mkdir()
        (nested_dir / "subdir" / "nested.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        src_dir = self.test_root / "src"
        (src_dir / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证嵌套的 data 目录中的文件没有被搜索
        for file_path in result:
            path_parts = file_path.replace("\\", "/").split("/")
            # 如果路径包含 data，应该不在搜索结果中
            if "data" in path_parts:
                # 找到 data 的位置
                data_index = path_parts.index("data")
                # 检查 data 之后是否还有文件（说明是嵌套的 data 目录）
                if data_index < len(path_parts) - 1:
                    self.fail(f"Found ignored file in nested data directory: {file_path}")
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_exclude_pycache_directory(self):
        """测试：排除 __pycache__ 目录及其内容"""
        # 创建应该被忽略的 __pycache__ 目录
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("search term\n", encoding="utf-8")
        (pycache_dir / "test.pyc").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证 __pycache__ 目录中的文件没有被搜索
        for file_path in result:
            self.assertNotIn("__pycache__", file_path)
            self.assertNotIn(".pyc", file_path)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_exclude_docs_directory(self):
        """测试：排除 docs/ 目录及其内容"""
        # 创建应该被忽略的 docs 目录（使用实际项目的.gitignore规则）
        docs_dir = self.test_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("search term\n", encoding="utf-8")
        (docs_dir / "api").mkdir()
        (docs_dir / "api" / "reference.md").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证 docs 目录中的文件没有被搜索
        for file_path in result:
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("docs", path_parts)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_exclude_semantic_cache_directory(self):
        """测试：排除 .semantic_cache/ 目录及其内容"""
        # 创建应该被忽略的 .semantic_cache 目录（使用实际项目的.gitignore规则）
        cache_dir = self.test_root / ".semantic_cache"
        cache_dir.mkdir()
        (cache_dir / "index.bin").write_text("search term\n", encoding="utf-8")
        (cache_dir / "metadata.json").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证 .semantic_cache 目录中的文件没有被搜索
        for file_path in result:
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn(".semantic_cache", path_parts)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_include_non_ignored_files(self):
        """测试：包含未被忽略的文件"""
        # 创建应该被忽略的文件
        (self.test_root / "ignored.pyc").write_text("search term\n", encoding="utf-8")
        ignored_dir = self.test_root / "data"
        ignored_dir.mkdir()
        (ignored_dir / "ignored.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")
        (self.test_root / "utils.py").write_text("search term\n", encoding="utf-8")
        (self.test_root / "config.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # 验证所有匹配的文件都是未被忽略的文件
        found_files = set(result)
        for file_path in found_files:
            # 验证不是被忽略的文件
            self.assertNotIn(".pyc", file_path)
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)

        # 验证找到了预期的文件
        main_path = str(self.test_root / "main.py")
        utils_path = str(self.test_root / "utils.py")
        config_path = str(self.test_root / "config.py")

        found_main = any(main_path in f for f in found_files)
        found_utils = any(utils_path in f for f in found_files)
        found_config = any(config_path in f for f in found_files)

        self.assertTrue(found_main or found_utils or found_config)

    def test_multiple_ignore_patterns(self):
        """测试：多个忽略模式同时生效"""
        # 创建多种应该被忽略的文件（使用实际项目的.gitignore规则）
        (self.test_root / "file1.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "file2.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "config.json").write_text('{"key": "search term"}\n', encoding="utf-8")
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "file4.pyc").write_text("search term\n", encoding="utf-8")
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "file5.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证所有被忽略的文件都没有被搜索
        for file_path in result:
            self.assertNotIn(".pyc", file_path)
            self.assertNotIn("config.json", file_path)
            self.assertNotIn("__pycache__", file_path)
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_file_type_filter_with_gitignore(self):
        """测试：文件类型过滤与 .gitignore 结合"""
        # 创建应该被忽略的文件
        (self.test_root / "ignored.pyc").write_text("search term\n", encoding="utf-8")
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的 Python 文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")
        (self.test_root / "utils.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索，只搜索 .py 文件
        result = grep("search term", path=str(self.test_root), file_type="*.py", output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证所有匹配的文件都是 .py 文件且未被忽略
        for file_path in result:
            self.assertTrue(file_path.endswith(".py"))
            self.assertNotIn(".pyc", file_path)
            self.assertNotIn("__pycache__", file_path)

    def test_output_mode_content_with_gitignore(self):
        """测试：输出模式 content 与 .gitignore 结合"""
        # 创建应该被忽略的文件（使用实际项目的.gitignore规则）
        (self.test_root / "ignored.pyc").write_text("search term\n", encoding="utf-8")
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "ignored.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="content")

        # 验证结果
        self.assertIsInstance(result, str)
        # 验证被忽略的文件不在结果中
        self.assertNotIn(".pyc", result)
        self.assertNotIn("data", result)
        # 验证未被忽略的文件在结果中
        self.assertIn("main.py", result)

    def test_output_mode_count_with_gitignore(self):
        """测试：输出模式 count 与 .gitignore 结合"""
        # 创建应该被忽略的文件（使用实际项目的.gitignore规则）
        (self.test_root / "ignored.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "ignored2.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "config.json").write_text('{"key": "search term"}\n', encoding="utf-8")
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "ignored.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")
        (self.test_root / "utils.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="count")

        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("total_matches", result)
        self.assertIn("files_with_matches", result)
        self.assertIn("files_searched", result)
        # 验证被忽略的文件没有被搜索
        self.assertLess(result["files_searched"], 5)  # 应该只搜索未被忽略的文件

    def test_gitignore_pattern_matching_wildcard(self):
        """测试：.gitignore 通配符模式匹配"""
        # 创建应该被忽略的文件（匹配通配符模式 *.pyc）
        (self.test_root / "file1.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "file2.pyc").write_text("search term\n", encoding="utf-8")
        (self.test_root / "any.pyc").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证所有 .pyc 文件都没有被搜索（通配符模式匹配）
        for file_path in result:
            self.assertNotIn(".pyc", file_path)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_gitignore_exact_filename(self):
        """测试：.gitignore 精确文件名匹配"""
        # 创建应该被忽略的文件（匹配精确文件名 config.json）
        (self.test_root / "config.json").write_text('{"key": "search term"}\n', encoding="utf-8")
        (self.test_root / "other.json").write_text('{"key": "search term"}\n', encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证 config.json 没有被搜索（精确匹配）
        for file_path in result:
            self.assertNotIn("config.json", file_path)
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))


    def test_nested_ignored_directories_deep(self):
        """测试：深层嵌套的忽略目录"""
        # 创建深层嵌套的忽略目录结构
        deep_nested_dir = self.test_root / "level1" / "level2" / "data"
        deep_nested_dir.mkdir(parents=True)
        (deep_nested_dir / "file.txt").write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        level1_dir = self.test_root / "level1"
        (level1_dir / "main.py").write_text("search term\n", encoding="utf-8")

        # 执行搜索
        result = grep("search term", path=str(self.test_root), output_mode="files")

        # 验证结果
        self.assertIsInstance(result, list)
        # 验证深层嵌套的 data 目录中的文件没有被搜索
        for file_path in result:
            path_parts = file_path.replace("\\", "/").split("/")
            # 如果路径包含 data，应该不在搜索结果中
            if "data" in path_parts:
                data_index = path_parts.index("data")
                if data_index < len(path_parts) - 1:
                    self.fail(f"Found ignored file in deep nested data directory: {file_path}")
        # 验证未被忽略的文件被搜索
        self.assertTrue(any("main.py" in f for f in result))

    def test_single_file_search_with_gitignore(self):
        """测试：搜索单个文件时 .gitignore 的处理"""
        # 创建应该被忽略的文件（使用实际项目的.gitignore规则：*.pyc）
        ignored_file = self.test_root / "ignored.pyc"
        ignored_file.write_text("search term\n", encoding="utf-8")

        # 创建不应该被忽略的文件
        main_file = self.test_root / "main.py"
        main_file.write_text("search term\n", encoding="utf-8")

        # 尝试搜索被忽略的文件（应该被排除）
        result = grep("search term", path=str(ignored_file), output_mode="files")

        # 验证结果（被忽略的文件不应该被搜索）
        self.assertIsInstance(result, list)
        # 如果文件被忽略，应该返回空列表或找不到匹配
        if len(result) == 0:
            # 这是预期的行为
            pass
        else:
            # 如果返回了结果，验证不是被忽略的文件
            for file_path in result:
                self.assertNotIn(".pyc", file_path)

        # 搜索未被忽略的文件（应该被搜索）
        result = grep("search term", path=str(main_file), output_mode="files")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertTrue(any("main.py" in f for f in result))


if __name__ == "__main__":
    # 抑制除了错误信息和结果信息以外的其他打印信息
    logging.basicConfig(level=logging.ERROR)
    
    unittest.main(verbosity=2)
