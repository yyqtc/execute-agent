#!/usr/bin/env python3
"""
测试 .gitignore 支持功能

该脚本用于验证以下函数是否正确实现了 .gitignore 支持：
1. tools/search.py 中的 grep 和 codebase_search 函数
2. utils/semantic_grep.py 中的 collect_files 函数
3. tools/gitignore.py 模块的功能
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入要测试的函数
from tools.search import grep, codebase_search
from tools.gitignore import load_gitignore_patterns, is_path_ignored, get_project_root

# 尝试导入 collect_files，如果失败则跳过相关测试
try:
    from utils.semantic_grep import collect_files

    SEMANTIC_GREP_AVAILABLE = True
except ImportError:
    SEMANTIC_GREP_AVAILABLE = False
    print("警告: 无法导入 utils.semantic_grep，将跳过 collect_files 测试")


def create_test_structure(base_dir):
    """创建测试目录结构"""
    # 创建目录
    os.makedirs(os.path.join(base_dir, "src"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "tests"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, ".git"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "__pycache__"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "node_modules"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "build"), exist_ok=True)

    # 创建文件
    with open(os.path.join(base_dir, "src", "main.py"), "w") as f:
        f.write("def main():\n    print('Hello')\n")

    with open(os.path.join(base_dir, "src", "utils.py"), "w") as f:
        f.write("def helper():\n    pass\n")

    with open(os.path.join(base_dir, "tests", "test_main.py"), "w") as f:
        f.write("def test_main():\n    pass\n")

    with open(os.path.join(base_dir, "__pycache__", "main.cpython-39.pyc"), "w") as f:
        f.write("binary content")

    with open(os.path.join(base_dir, "node_modules", "package.json"), "w") as f:
        f.write('{"name": "test"}\n')

    with open(os.path.join(base_dir, "build", "output.txt"), "w") as f:
        f.write("build output\n")

    # 创建 .gitignore 文件
    gitignore_content = """# Python
__pycache__/
*.pyc
*.pyo

# Node modules
node_modules/

# Build
build/

# But include this file in build
!build/important.txt
"""
    with open(os.path.join(base_dir, ".gitignore"), "w") as f:
        f.write(gitignore_content)

    # 创建被否定模式包含的文件
    with open(os.path.join(base_dir, "build", "important.txt"), "w") as f:
        f.write("important file\n")


def test_gitignore_module():
    """测试 tools/gitignore.py 模块"""
    print("测试 tools/gitignore.py 模块...")

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_structure(tmpdir)

        # 测试 load_gitignore_patterns
        ignore_patterns, negation_patterns = load_gitignore_patterns(tmpdir)
        assert len(ignore_patterns) > 0, "应该加载到忽略模式"
        assert (
            "__pycache__/" in ignore_patterns or "__pycache__" in ignore_patterns
        ), "应该包含 __pycache__ 模式"

        # 测试 is_path_ignored
        assert is_path_ignored(
            "__pycache__/main.pyc", ignore_patterns, negation_patterns
        ), "__pycache__ 应该被忽略"
        assert is_path_ignored(
            "node_modules/package.json", ignore_patterns, negation_patterns
        ), "node_modules 应该被忽略"
        assert is_path_ignored(
            "build/output.txt", ignore_patterns, negation_patterns
        ), "build 应该被忽略"
        assert not is_path_ignored(
            "build/important.txt", ignore_patterns, negation_patterns
        ), "build/important.txt 不应该被忽略（否定模式）"
        assert not is_path_ignored(
            "src/main.py", ignore_patterns, negation_patterns
        ), "src/main.py 不应该被忽略"

        print("  tools/gitignore.py 模块测试通过")


def test_collect_files():
    """测试 utils/semantic_grep.py 中的 collect_files 函数"""
    if not SEMANTIC_GREP_AVAILABLE:
        print("  跳过 collect_files 测试（模块不可用）")
        return

    print("测试 utils/semantic_grep.py 中的 collect_files 函数...")

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_structure(tmpdir)

        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # 测试收集文件
            files = collect_files(".", file_type="*.py")

            # 验证被忽略的文件不在结果中
            file_paths = [os.path.normpath(f) for f in files]
            assert not any(
                "__pycache__" in f for f in file_paths
            ), "不应该包含 __pycache__ 中的文件"
            assert not any(
                "node_modules" in f for f in file_paths
            ), "不应该包含 node_modules 中的文件"
            assert not any(
                "build/output.txt" in f for f in file_paths
            ), "不应该包含 build/output.txt"

            # 验证应该包含的文件在结果中
            assert any("src/main.py" in f for f in file_paths), "应该包含 src/main.py"
            assert any("src/utils.py" in f for f in file_paths), "应该包含 src/utils.py"
            assert any(
                "tests/test_main.py" in f for f in file_paths
            ), "应该包含 tests/test_main.py"

            print("  collect_files 函数测试通过")
        finally:
            os.chdir(original_cwd)


def test_grep():
    """测试 tools/search.py 中的 grep 函数"""
    print("测试 tools/search.py 中的 grep 函数...")

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_structure(tmpdir)

        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # 测试 grep 搜索
            result = grep("def", path=".", file_type="*.py", output_mode="files")

            # 验证被忽略的文件不在结果中
            assert isinstance(result, list), "应该返回文件列表"
            file_paths = [os.path.normpath(f) for f in result]
            assert not any(
                "__pycache__" in f for f in file_paths
            ), "不应该包含 __pycache__ 中的文件"
            assert not any(
                "node_modules" in f for f in file_paths
            ), "不应该包含 node_modules 中的文件"

            # 验证应该包含的文件在结果中
            assert any("src/main.py" in f for f in file_paths), "应该包含 src/main.py"
            assert any("src/utils.py" in f for f in file_paths), "应该包含 src/utils.py"
            assert any(
                "tests/test_main.py" in f for f in file_paths
            ), "应该包含 tests/test_main.py"

            print("  grep 函数测试通过")
        finally:
            os.chdir(original_cwd)


def test_codebase_search():
    """测试 tools/search.py 中的 codebase_search 函数"""
    print("测试 tools/search.py 中的 codebase_search 函数...")

    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_structure(tmpdir)

        # 切换到测试目录
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # 测试 codebase_search
            result_str = codebase_search(
                "def", target_directories=["."], file_pattern="*.py"
            )
            result = json.loads(result_str)

            # 验证结果结构
            assert "matches" in result, "应该包含 matches 字段"
            assert (
                "total_files_searched" in result
            ), "应该包含 total_files_searched 字段"

            # 验证被忽略的文件不在结果中
            file_paths = [m["file_path"] for m in result["matches"]]
            file_paths_normalized = [os.path.normpath(f) for f in file_paths]
            assert not any(
                "__pycache__" in f for f in file_paths_normalized
            ), "不应该包含 __pycache__ 中的文件"
            assert not any(
                "node_modules" in f for f in file_paths_normalized
            ), "不应该包含 node_modules 中的文件"

            # 验证应该包含的文件在结果中（至少搜索过）
            assert result["total_files_searched"] > 0, "应该搜索到文件"

            print("  codebase_search 函数测试通过")
        finally:
            os.chdir(original_cwd)


def main():
    """运行所有测试"""
    print("开始测试 .gitignore 支持功能...\n")

    try:
        test_gitignore_module()
        if SEMANTIC_GREP_AVAILABLE:
            test_collect_files()
        test_grep()
        test_codebase_search()

        print("\n所有测试通过！")
        return 0
    except AssertionError as e:
        print(f"\n测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
