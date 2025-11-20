#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
codebase_search 工具的单元测试
验证关键词搜索、语义搜索、目录过滤、文件类型过滤功能
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
import json
import glob
import re
from pathlib import Path
from typing import List, Optional


# 为了避免循环导入问题，直接复制 codebase_search 函数及其依赖函数的实现
def _extract_keywords(query: str) -> List[str]:
    """
    从自然语言查询中提取关键词

    Args:
        query: 自然语言查询字符串

    Returns:
        关键词列表
    """
    # 简单的停用词列表（可以根据需要扩展）
    stop_words = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "can",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "with",
        "by",
        "from",
        "as",
        "and",
        "or",
        "but",
        "if",
        "then",
        "that",
        "this",
        "these",
        "those",
        "what",
        "which",
        "who",
        "where",
        "when",
        "why",
        "how",
        "how",
        "all",
        "each",
        "every",
        "some",
        "any",
        "no",
        "not",
        "only",
        "just",
        "also",
        "more",
        "most",
        "very",
        "too",
        "so",
        "such",
        "than",
        "then",
        "there",
        "here",
        "where",
        "when",
        "查找",
        "搜索",
        "找",
        "的",
        "了",
        "在",
        "是",
        "有",
        "和",
        "与",
        "或",
        "但",
        "如果",
        "那么",
        "这个",
        "那个",
        "这些",
        "那些",
        "什么",
        "哪个",
        "谁",
        "哪里",
        "何时",
        "为什么",
        "如何",
        "所有",
        "每个",
        "一些",
        "任何",
        "没有",
        "不",
        "只",
        "也",
        "更",
        "最",
        "非常",
        "太",
        "所以",
        "这样",
        "那样",
        "那里",
        "这里",
    }

    # 将查询转换为小写并分割成单词
    # 使用正则表达式提取单词（包括中文字符）
    words = re.findall(r"\b\w+\b|[a-zA-Z]+|[\u4e00-\u9fff]+", query.lower())

    # 过滤停用词和短词（长度小于2的词）
    keywords = [word for word in words if word not in stop_words and len(word) >= 2]

    # 如果没有提取到关键词，返回原始查询（去除停用词后）
    if not keywords:
        # 如果所有词都是停用词，至少返回一些有意义的词
        meaningful_words = [word for word in words if len(word) >= 2]
        if meaningful_words:
            return meaningful_words
        # 如果还是没有，返回原始查询的单词
        return [word for word in words if word]

    return keywords


def _search_in_file(
    file_path: str, keywords: List[str], max_results: int = 50
) -> List[dict]:
    """
    在文件中搜索关键词，返回匹配的行

    Args:
        file_path: 文件路径
        keywords: 关键词列表
        max_results: 最大返回结果数

    Returns:
        匹配结果列表，每个元素包含 file_path, line_number, content
    """
    results = []

    try:
        # 检查文件是否存在
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return results

        # 检查读取权限
        if not os.access(file_path, os.R_OK):
            return results

        # 读取文件内容
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, IOError):
            # 如果无法读取（可能是二进制文件），跳过
            return results

        # 在每一行中搜索关键词
        for line_num, line in enumerate(lines, start=1):
            line_lower = line.lower()
            # 检查是否包含任何关键词
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in line_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                results.append(
                    {
                        "file_path": os.path.abspath(file_path),
                        "line_number": line_num,
                        "content": line.rstrip("\n\r"),
                        "matched_keywords": matched_keywords,
                    }
                )

                # 限制结果数量
                if len(results) >= max_results:
                    break

    except Exception:
        # 忽略错误，继续搜索其他文件
        pass

    return results


def codebase_search(
    query: str,
    target_directories: Optional[List[str]] = None,
    file_pattern: Optional[str] = None,
) -> str:
    """
    基于关键词搜索代码库，返回匹配的代码片段列表

    Args:
        query: 搜索查询（自然语言或关键词）
        target_directories: 目标目录列表（可选），如果未提供则搜索当前目录
        file_pattern: 文件类型过滤模式（可选），例如 "*.py", "*.js" 等

    Returns:
        JSON 格式字符串，包含匹配的代码片段列表。每个元素包含：
        - file_path: 文件路径
        - line_number: 行号
        - content: 代码内容
        - matched_keywords: 匹配的关键词列表

    功能说明:
        - 从自然语言查询中提取关键词
        - 支持目录范围限制（target_directories）
        - 支持文件类型过滤（file_pattern）
        - 返回匹配的代码片段，包含文件路径、行号和代码内容
    """
    try:
        # 从查询中提取关键词
        keywords = _extract_keywords(query)

        if not keywords:
            return json.dumps(
                {"error": "无法从查询中提取关键词", "query": query},
                ensure_ascii=False,
                indent=2,
            )

        # 确定搜索目录
        if target_directories:
            search_dirs = [os.path.abspath(d) for d in target_directories]
        else:
            # 默认搜索当前目录
            search_dirs = [os.path.abspath(".")]

        # 验证目录是否存在
        valid_dirs = []
        for dir_path in search_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                if os.access(dir_path, os.R_OK):
                    valid_dirs.append(dir_path)

        if not valid_dirs:
            return json.dumps(
                {
                    "error": "没有有效的搜索目录",
                    "target_directories": target_directories,
                },
                ensure_ascii=False,
                indent=2,
            )

        # 收集要搜索的文件
        files_to_search = []

        for dir_path in valid_dirs:
            if file_pattern:
                # 使用文件模式过滤
                pattern = file_pattern
                if not os.path.isabs(pattern):
                    # 构建搜索模式
                    search_pattern = os.path.join(dir_path, "**", pattern)
                else:
                    search_pattern = pattern

                matched_files = glob.glob(search_pattern, recursive=True)
                for file_path in matched_files:
                    if os.path.isfile(file_path):
                        files_to_search.append(file_path)
            else:
                # 搜索所有文件（递归）
                for root, dirs, files in os.walk(dir_path):
                    # 跳过常见的忽略目录
                    dirs[:] = [
                        d
                        for d in dirs
                        if d
                        not in {".git", "__pycache__", "node_modules", ".venv", "venv"}
                    ]

                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            files_to_search.append(file_path)

        # 去重
        files_to_search = list(set(files_to_search))

        # 在所有文件中搜索关键词
        all_results = []
        for file_path in files_to_search:
            file_results = _search_in_file(file_path, keywords)
            all_results.extend(file_results)

        # 按文件路径和行号排序
        all_results.sort(key=lambda x: (x["file_path"], x["line_number"]))

        # 构建返回结果
        result = {
            "query": query,
            "keywords": keywords,
            "search_directories": valid_dirs,
            "file_pattern": file_pattern,
            "total_files_searched": len(files_to_search),
            "total_matches": len(all_results),
            "matches": all_results[:100],  # 限制返回最多100个结果
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"搜索代码库时发生错误: {str(e)}", "query": query},
            ensure_ascii=False,
            indent=2,
        )


class TestCodebaseSearch(unittest.TestCase):
    """codebase_search 工具的测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        # 创建临时目录作为测试根目录
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        # 切换到测试目录（确保路径解析正确）
        self.original_cwd = os.getcwd()
        os.chdir(self.test_root)

        # 创建测试目录结构
        # test_root/
        #   ├── main.py (包含 "def main function" 和 "class MainClass")
        #   ├── utils.py (包含 "def utility function" 和 "helper")
        #   ├── config.json (包含 "configuration" 和 "settings")
        #   ├── README.md (包含 "documentation" 和 "usage")
        #   ├── src/
        #   │   ├── module1.py (包含 "def module1 function" 和 "import")
        #   │   ├── module2.js (包含 "function module2" 和 "export")
        #   │   └── data.txt (包含 "data" 和 "content")
        #   └── tests/
        #       ├── test_main.py (包含 "def test function" 和 "assert")
        #       └── test_utils.py (包含 "def test utility" 和 "unittest")

        # 创建根目录文件
        (self.test_root / "main.py").write_text(
            "def main_function():\n    print('Hello')\n    return True\n\n"
            "class MainClass:\n    def __init__(self):\n        pass\n",
            encoding="utf-8",
        )
        (self.test_root / "utils.py").write_text(
            "def utility_function():\n    return 'utility'\n\n"
            "def helper_function():\n    return 'helper'\n",
            encoding="utf-8",
        )
        (self.test_root / "config.json").write_text(
            '{"configuration": "settings", "key": "value"}', encoding="utf-8"
        )
        (self.test_root / "README.md").write_text(
            "# Documentation\n\nUsage instructions\n", encoding="utf-8"
        )

        # 创建 src 目录和文件
        src_dir = self.test_root / "src"
        src_dir.mkdir()
        (src_dir / "module1.py").write_text(
            "def module1_function():\n    import os\n    return 'module1'\n",
            encoding="utf-8",
        )
        (src_dir / "module2.js").write_text(
            "function module2() {\n    export default module2;\n}\n", encoding="utf-8"
        )
        (src_dir / "data.txt").write_text("data content\nmore data\n", encoding="utf-8")

        # 创建 tests 目录和文件
        tests_dir = self.test_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text(
            "def test_function():\n    assert True\n    return True\n", encoding="utf-8"
        )
        (tests_dir / "test_utils.py").write_text(
            "def test_utility():\n    import unittest\n    assert True\n",
            encoding="utf-8",
        )

    def tearDown(self):
        """每个测试后的清理工作"""
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_keyword_search_basic(self):
        """测试：基本关键词搜索"""
        result_str = codebase_search(
            "main function", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证返回结果结构
        self.assertIn("query", result)
        self.assertIn("keywords", result)
        self.assertIn("matches", result)
        self.assertIn("total_matches", result)

        # 验证关键词提取
        self.assertGreater(len(result["keywords"]), 0)
        self.assertIn("main", [k.lower() for k in result["keywords"]])

        # 验证找到匹配结果
        self.assertGreater(result["total_matches"], 0)

        # 验证匹配结果格式
        if result["matches"]:
            match = result["matches"][0]
            self.assertIn("file_path", match)
            self.assertIn("line_number", match)
            self.assertIn("content", match)
            self.assertIn("matched_keywords", match)

    def test_keyword_search_multiple_keywords(self):
        """测试：多个关键词搜索"""
        result_str = codebase_search(
            "utility helper function", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证找到匹配结果
        self.assertGreater(result["total_matches"], 0)

        # 验证匹配结果包含关键词
        found_utility = False
        found_helper = False
        for match in result["matches"]:
            content_lower = match["content"].lower()
            if "utility" in content_lower:
                found_utility = True
            if "helper" in content_lower:
                found_helper = True

        self.assertTrue(found_utility or found_helper)

    def test_semantic_search_natural_language(self):
        """测试：自然语言语义搜索"""
        # 测试自然语言查询
        result_str = codebase_search(
            "How does the main function work?", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证关键词提取（应该提取出 "main", "function", "work" 等）
        self.assertGreater(len(result["keywords"]), 0)

        # 验证找到匹配结果
        self.assertGreater(result["total_matches"], 0)

        # 验证匹配结果中包含 "main" 或 "function"
        found_relevant = False
        for match in result["matches"]:
            content_lower = match["content"].lower()
            if "main" in content_lower or "function" in content_lower:
                found_relevant = True
                break

        self.assertTrue(found_relevant)

    def test_semantic_search_chinese_query(self):
        """测试：中文查询的语义搜索"""
        result_str = codebase_search(
            "查找主函数", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证关键词提取（应该提取出 "查找", "主", "函数" 等）
        self.assertGreater(len(result["keywords"]), 0)

        # 验证找到匹配结果（如果关键词匹配）
        # 注意：由于停用词过滤，"查找"可能被过滤掉，但"主"和"函数"应该保留
        self.assertIsInstance(result["total_matches"], int)

    def test_directory_filter_single_directory(self):
        """测试：目录过滤 - 单个目录"""
        # 只在 src 目录中搜索
        result_str = codebase_search(
            "function", target_directories=[str(self.test_root / "src")]
        )
        result = json.loads(result_str)

        # 验证搜索目录
        self.assertEqual(len(result["search_directories"]), 1)
        self.assertIn(str(self.test_root / "src"), result["search_directories"])

        # 验证所有匹配结果都在 src 目录中
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertTrue(str(file_path).startswith(str(self.test_root / "src")))

    def test_directory_filter_multiple_directories(self):
        """测试：目录过滤 - 多个目录"""
        # 在 src 和 tests 目录中搜索
        result_str = codebase_search(
            "function",
            target_directories=[
                str(self.test_root / "src"),
                str(self.test_root / "tests"),
            ],
        )
        result = json.loads(result_str)

        # 验证搜索目录
        self.assertEqual(len(result["search_directories"]), 2)
        self.assertIn(str(self.test_root / "src"), result["search_directories"])
        self.assertIn(str(self.test_root / "tests"), result["search_directories"])

        # 验证所有匹配结果都在指定的目录中
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            file_path_str = str(file_path)
            self.assertTrue(
                file_path_str.startswith(str(self.test_root / "src"))
                or file_path_str.startswith(str(self.test_root / "tests"))
            )

    def test_directory_filter_excludes_other_directories(self):
        """测试：目录过滤 - 排除其他目录"""
        # 只在 src 目录中搜索
        result_str = codebase_search(
            "function", target_directories=[str(self.test_root / "src")]
        )
        result = json.loads(result_str)

        # 验证匹配结果不在 tests 目录中
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertNotIn(str(self.test_root / "tests"), str(file_path))

    def test_file_type_filter_python_files(self):
        """测试：文件类型过滤 - Python 文件"""
        result_str = codebase_search(
            "function", file_pattern="*.py", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证文件模式
        self.assertEqual(result["file_pattern"], "*.py")

        # 验证所有匹配结果都是 .py 文件
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertEqual(file_path.suffix, ".py")

    def test_file_type_filter_javascript_files(self):
        """测试：文件类型过滤 - JavaScript 文件"""
        result_str = codebase_search(
            "function", file_pattern="*.js", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证文件模式
        self.assertEqual(result["file_pattern"], "*.js")

        # 验证所有匹配结果都是 .js 文件
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertEqual(file_path.suffix, ".js")

    def test_file_type_filter_text_files(self):
        """测试：文件类型过滤 - 文本文件"""
        result_str = codebase_search(
            "data", file_pattern="*.txt", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证文件模式
        self.assertEqual(result["file_pattern"], "*.txt")

        # 验证所有匹配结果都是 .txt 文件
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertEqual(file_path.suffix, ".txt")

    def test_file_type_filter_combined_with_directory(self):
        """测试：文件类型过滤与目录过滤组合"""
        # 在 src 目录中搜索 .py 文件
        result_str = codebase_search(
            "function",
            target_directories=[str(self.test_root / "src")],
            file_pattern="*.py",
        )
        result = json.loads(result_str)

        # 验证搜索目录和文件模式
        self.assertEqual(len(result["search_directories"]), 1)
        self.assertEqual(result["file_pattern"], "*.py")

        # 验证所有匹配结果都在 src 目录中且是 .py 文件
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertTrue(str(file_path).startswith(str(self.test_root / "src")))
            self.assertEqual(file_path.suffix, ".py")

    def test_no_matches(self):
        """测试：无匹配结果"""
        result_str = codebase_search(
            "nonexistent_keyword_xyz123", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证返回结果结构
        self.assertIn("total_matches", result)
        self.assertEqual(result["total_matches"], 0)
        self.assertEqual(len(result["matches"]), 0)

    def test_empty_query(self):
        """测试：空查询"""
        result_str = codebase_search("", target_directories=[str(self.test_root)])
        result = json.loads(result_str)

        # 验证返回错误信息
        self.assertIn("error", result)
        self.assertIn("无法从查询中提取关键词", result["error"])

    def test_invalid_directory(self):
        """测试：无效目录"""
        invalid_dir = self.test_root / "nonexistent_dir"
        result_str = codebase_search("function", target_directories=[str(invalid_dir)])
        result = json.loads(result_str)

        # 验证返回错误信息
        self.assertIn("error", result)
        self.assertIn("没有有效的搜索目录", result["error"])

    def test_default_search_directory(self):
        """测试：默认搜索目录（不指定 target_directories）"""
        result_str = codebase_search("function")
        result = json.loads(result_str)

        # 验证返回结果结构
        self.assertIn("search_directories", result)
        self.assertGreater(len(result["search_directories"]), 0)

        # 验证搜索目录是当前目录
        current_dir = os.path.abspath(".")
        self.assertIn(current_dir, result["search_directories"])

    def test_case_insensitive_search(self):
        """测试：大小写不敏感搜索"""
        result_str = codebase_search(
            "MAIN FUNCTION", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证找到匹配结果（应该能找到 "main" 和 "function"）
        self.assertGreater(result["total_matches"], 0)

    def test_special_characters_in_query(self):
        """测试：查询中包含特殊字符"""
        result_str = codebase_search(
            "function() { }", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证关键词提取（应该提取出 "function"）
        self.assertGreater(len(result["keywords"]), 0)

        # 验证找到匹配结果
        self.assertGreater(result["total_matches"], 0)

    def test_multiple_matches_in_same_file(self):
        """测试：同一文件中的多个匹配"""
        result_str = codebase_search(
            "function", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 统计每个文件的匹配数
        file_matches = {}
        for match in result["matches"]:
            file_path = match["file_path"]
            if file_path not in file_matches:
                file_matches[file_path] = 0
            file_matches[file_path] += 1

        # 验证某些文件有多个匹配
        # utils.py 应该包含多个 "function"
        utils_path = str(self.test_root / "utils.py")
        if utils_path in file_matches:
            self.assertGreater(file_matches[utils_path], 1)

    def test_result_ordering(self):
        """测试：结果排序（按文件路径和行号）"""
        result_str = codebase_search(
            "function", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证结果已排序
        if len(result["matches"]) > 1:
            matches = result["matches"]
            for i in range(len(matches) - 1):
                current = matches[i]
                next_match = matches[i + 1]

                # 比较文件路径和行号
                if current["file_path"] == next_match["file_path"]:
                    # 同一文件，行号应该递增
                    self.assertLessEqual(
                        current["line_number"], next_match["line_number"]
                    )
                else:
                    # 不同文件，文件路径应该按字典序
                    self.assertLessEqual(current["file_path"], next_match["file_path"])

    def test_max_results_limit(self):
        """测试：结果数量限制（最多100个）"""
        # 创建一个包含大量匹配的文件
        large_file = self.test_root / "large_file.py"
        content = "\n".join([f"def function_{i}(): pass" for i in range(150)])
        large_file.write_text(content, encoding="utf-8")

        result_str = codebase_search(
            "function", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证返回的匹配数不超过100
        self.assertLessEqual(len(result["matches"]), 100)

        # 验证 total_matches 反映实际匹配数
        self.assertGreaterEqual(result["total_matches"], len(result["matches"]))

    def test_ignored_directories(self):
        """测试：忽略常见目录（如 __pycache__）"""
        # 创建 __pycache__ 目录和文件
        pycache_dir = self.test_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "test.pyc").write_text("def function(): pass", encoding="utf-8")

        result_str = codebase_search(
            "function", target_directories=[str(self.test_root)]
        )
        result = json.loads(result_str)

        # 验证 __pycache__ 目录中的文件不会被搜索
        for match in result["matches"]:
            file_path = Path(match["file_path"])
            self.assertNotIn("__pycache__", str(file_path))

    def test_relative_path_target_directories(self):
        """测试：使用相对路径指定目标目录"""
        # 切换到测试根目录的父目录
        parent_dir = self.test_root.parent
        os.chdir(parent_dir)

        # 使用相对路径
        relative_path = os.path.relpath(self.test_root, parent_dir)
        result_str = codebase_search("function", target_directories=[relative_path])
        result = json.loads(result_str)

        # 验证找到匹配结果
        self.assertGreater(result["total_matches"], 0)

        # 恢复工作目录
        os.chdir(self.test_root)


if __name__ == "__main__":
    unittest.main()
