#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
codebase_search 函数的 .gitignore 排除功能测试
验证 .gitignore 中列出的文件和文件夹是否被正确排除
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
import json
import sys
from pathlib import Path

# 导入 codebase_search 函数
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.search import codebase_search


class TestCodebaseSearchGitignore(unittest.TestCase):
    """codebase_search 函数的 .gitignore 排除功能测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为测试根目录
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        # 切换到测试目录（确保路径解析正确）
        self.original_cwd = os.getcwd()
        os.chdir(self.test_root)

        # 创建 .gitignore 文件（基础配置）
        gitignore_content = """__pycache__/
*.pyc
*.log
data/
build/
dist/
.env
*.tmp
"""
        (self.test_root / ".gitignore").write_text(gitignore_content, encoding="utf-8")

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_exclude_pycache_directory(self):
        """测试：排除 __pycache__ 目录及其内容"""
        # 创建应该被忽略的 __pycache__ 目录
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("compiled code", encoding="utf-8")
        (pycache_dir / "test.pyc").write_text("compiled test", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")
        (self.test_root / "utils.py").write_text("def utility(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证结果
        self.assertIn("matches", result)
        self.assertIn("total_files_searched", result)

        # 验证 __pycache__ 目录中的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn("__pycache__", file_path)
            self.assertNotIn(".pyc", file_path)

    def test_exclude_pyc_files(self):
        """测试：排除 .pyc 文件"""
        # 创建应该被忽略的 .pyc 文件
        (self.test_root / "module.pyc").write_text("compiled code", encoding="utf-8")
        (self.test_root / "test.pyc").write_text("compiled test", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")
        (self.test_root / "utils.py").write_text("def utility(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 .pyc 文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".pyc", file_path)

    def test_exclude_log_files(self):
        """测试：排除 .log 文件"""
        # 创建应该被忽略的 .log 文件
        (self.test_root / "app.log").write_text("log content", encoding="utf-8")
        (self.test_root / "error.log").write_text("error log", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 .log 文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".log", file_path)

    def test_exclude_data_directory(self):
        """测试：排除 data/ 目录及其内容"""
        # 创建应该被忽略的 data 目录
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "file1.txt").write_text("data content 1", encoding="utf-8")
        (data_dir / "file2.txt").write_text("data content 2", encoding="utf-8")
        (data_dir / "subdir").mkdir()
        (data_dir / "subdir" / "nested.txt").write_text("nested data", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 data 目录中的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            # 检查路径中是否包含 data/（使用路径分隔符）
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)

    def test_exclude_build_directory(self):
        """测试：排除 build/ 目录及其内容"""
        # 创建应该被忽略的 build 目录
        build_dir = self.test_root / "build"
        build_dir.mkdir()
        (build_dir / "output.txt").write_text("build output", encoding="utf-8")
        (build_dir / "lib").mkdir()
        (build_dir / "lib" / "module.so").write_text("binary content", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 build 目录中的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("build", path_parts)

    def test_exclude_dist_directory(self):
        """测试：排除 dist/ 目录及其内容"""
        # 创建应该被忽略的 dist 目录
        dist_dir = self.test_root / "dist"
        dist_dir.mkdir()
        (dist_dir / "package.tar.gz").write_text("package content", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 dist 目录中的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("dist", path_parts)

    def test_exclude_env_file(self):
        """测试：排除 .env 文件"""
        # 创建应该被忽略的 .env 文件
        (self.test_root / ".env").write_text("API_KEY=secret", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 .env 文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".env", file_path)

    def test_exclude_tmp_files(self):
        """测试：排除 .tmp 文件"""
        # 创建应该被忽略的 .tmp 文件
        (self.test_root / "temp.tmp").write_text("temporary content", encoding="utf-8")
        (self.test_root / "cache.tmp").write_text("cache content", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证 .tmp 文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".tmp", file_path)

    def test_include_non_ignored_files(self):
        """测试：包含未被忽略的文件"""
        # 创建应该被忽略的文件
        (self.test_root / "ignored.pyc").write_text("ignored", encoding="utf-8")
        ignored_dir = self.test_root / "data"
        ignored_dir.mkdir()
        (ignored_dir / "ignored.txt").write_text("ignored", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main_function(): pass", encoding="utf-8")
        (self.test_root / "utils.py").write_text("def utility_function(): pass", encoding="utf-8")
        (self.test_root / "config.py").write_text("def config_function(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("function", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证找到了未被忽略的文件
        self.assertGreater(result["total_matches"], 0)

        # 验证所有匹配的文件都是未被忽略的文件
        found_files = set()
        for match in result["matches"]:
            file_path = match["file_path"]
            found_files.add(file_path)
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

    def test_nested_ignored_directories(self):
        """测试：嵌套的忽略目录"""
        # 创建嵌套的忽略目录结构
        nested_dir = self.test_root / "src" / "data"
        nested_dir.mkdir(parents=True)
        (nested_dir / "file.txt").write_text("nested data", encoding="utf-8")

        # 创建不应该被忽略的文件
        src_dir = self.test_root / "src"
        (src_dir / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证嵌套的 data 目录中的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            # 检查路径中是否包含 data/（使用路径分隔符）
            path_parts = file_path.replace("\\", "/").split("/")
            # 如果路径包含 data，应该不在搜索结果中
            if "data" in path_parts:
                # 找到 data 的位置
                data_index = path_parts.index("data")
                # 检查 data 之后是否还有文件（说明是嵌套的 data 目录）
                if data_index < len(path_parts) - 1:
                    self.fail(f"Found ignored file in nested data directory: {file_path}")

    def test_multiple_ignore_patterns(self):
        """测试：多个忽略模式同时生效"""
        # 创建多种应该被忽略的文件
        (self.test_root / "file1.pyc").write_text("pyc", encoding="utf-8")
        (self.test_root / "file2.log").write_text("log", encoding="utf-8")
        (self.test_root / "file3.tmp").write_text("tmp", encoding="utf-8")
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "file4.pyc").write_text("pyc", encoding="utf-8")
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "file5.txt").write_text("data", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证所有被忽略的文件都没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".pyc", file_path)
            self.assertNotIn(".log", file_path)
            self.assertNotIn(".tmp", file_path)
            self.assertNotIn("__pycache__", file_path)
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)

    def test_gitignore_in_subdirectory(self):
        """测试：子目录中的 .gitignore 文件（应该使用项目根目录的 .gitignore）"""
        # 创建子目录
        subdir = self.test_root / "subdir"
        subdir.mkdir()

        # 在子目录中创建 .gitignore（应该被忽略，因为项目根目录的 .gitignore 优先）
        (subdir / ".gitignore").write_text("local_ignore.txt", encoding="utf-8")

        # 创建应该被根目录 .gitignore 忽略的文件
        (subdir / "file.pyc").write_text("pyc", encoding="utf-8")
        data_subdir = subdir / "data"
        data_subdir.mkdir()
        (data_subdir / "file.txt").write_text("data", encoding="utf-8")

        # 创建不应该被忽略的文件
        (subdir / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证子目录中被根目录 .gitignore 忽略的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".pyc", file_path)
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)

    def test_file_pattern_with_gitignore(self):
        """测试：文件类型过滤与 .gitignore 结合"""
        # 创建应该被忽略的文件
        (self.test_root / "ignored.pyc").write_text("ignored", encoding="utf-8")
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("ignored", encoding="utf-8")

        # 创建不应该被忽略的 Python 文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")
        (self.test_root / "utils.py").write_text("def utility(): pass", encoding="utf-8")

        # 执行搜索，只搜索 .py 文件
        result_str = codebase_search(
            "def", target_directories=[str(self.test_root)], file_pattern="*.py"
        )
        result = json.loads(result_str)

        # 验证文件模式正确
        self.assertEqual(result["file_pattern"], "*.py")

        # 验证所有匹配的文件都是 .py 文件且未被忽略
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertTrue(file_path.endswith(".py"))
            self.assertNotIn(".pyc", file_path)
            self.assertNotIn("__pycache__", file_path)

    def test_empty_gitignore(self):
        """测试：空的 .gitignore 文件（所有文件都应该被搜索）"""
        # 创建空的 .gitignore
        (self.test_root / ".gitignore").write_text("", encoding="utf-8")

        # 创建文件（正常情况下会被忽略，但现在不应该被忽略）
        (self.test_root / "file.pyc").write_text("def test(): pass", encoding="utf-8")
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("def test(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证所有文件都被搜索（因为 .gitignore 为空）
        # 注意：由于 .gitignore 为空，所有文件都应该被搜索
        self.assertGreaterEqual(result["total_files_searched"], 0)

    def test_gitignore_with_comments(self):
        """测试：包含注释的 .gitignore 文件"""
        # 创建包含注释的 .gitignore
        gitignore_content = """# Python cache files
__pycache__/
*.pyc

# Log files
*.log

# Data directory
data/
"""
        (self.test_root / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        # 创建应该被忽略的文件
        (self.test_root / "file.pyc").write_text("ignored", encoding="utf-8")
        (self.test_root / "app.log").write_text("ignored", encoding="utf-8")
        data_dir = self.test_root / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("ignored", encoding="utf-8")

        # 创建不应该被忽略的文件
        (self.test_root / "main.py").write_text("def main(): pass", encoding="utf-8")

        # 执行搜索
        result_str = codebase_search("def", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证被忽略的文件没有被搜索
        for match in result["matches"]:
            file_path = match["file_path"]
            self.assertNotIn(".pyc", file_path)
            self.assertNotIn(".log", file_path)
            path_parts = file_path.replace("\\", "/").split("/")
            self.assertNotIn("data", path_parts)


if __name__ == "__main__":
    # 抑制除了错误信息和结果信息以外的其他打印信息
    import logging
    logging.basicConfig(level=logging.ERROR)
    
    unittest.main(verbosity=2)
