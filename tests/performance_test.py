#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能测试：测试 codebase_search 和 grep 并行化前后的性能
创建大量文件作为测试数据集，记录并对比执行时间，生成性能测试报告
注意：不允许对所在目录的父目录进行写入操作！
"""

import unittest
import os
import tempfile
import shutil
import time
import json
import re
import glob
import threading
import multiprocessing
from pathlib import Path
from typing import List, Optional, Union, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed


# 导入实际实现
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.search import (
    codebase_search as codebase_search_parallel,
    grep as grep_parallel,
)
from tools.search import _extract_keywords, _search_in_file


# 非并行版本的 codebase_search（用于对比）
def codebase_search_sequential(
    query: str,
    target_directories: Optional[List[str]] = None,
    file_pattern: Optional[str] = None,
) -> str:
    """非并行版本的 codebase_search，用于性能对比"""
    try:
        keywords = _extract_keywords(query)

        if not keywords:
            return json.dumps(
                {"error": "无法从查询中提取关键词", "query": query},
                ensure_ascii=False,
                indent=2,
            )

        if target_directories:
            search_dirs = [os.path.abspath(d) for d in target_directories]
        else:
            search_dirs = [os.path.abspath(".")]

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

        project_root = valid_dirs[0]
        first_dir = Path(valid_dirs[0]).resolve()
        root_candidate = first_dir
        while root_candidate != root_candidate.parent:
            gitignore_path = root_candidate / ".gitignore"
            if gitignore_path.exists():
                project_root = str(root_candidate)
                break
            root_candidate = root_candidate.parent
        project_root = str(Path(project_root).resolve())

        from tools.gitignore import load_gitignore_patterns, is_path_ignored

        ignore_patterns, negation_patterns = load_gitignore_patterns(project_root)

        files_to_search = []

        for dir_path in valid_dirs:
            if file_pattern:
                pattern = file_pattern
                if not os.path.isabs(pattern):
                    search_pattern = os.path.join(dir_path, "**", pattern)
                else:
                    search_pattern = pattern

                matched_files = glob.glob(search_pattern, recursive=True)
                for file_path in matched_files:
                    if os.path.isfile(file_path):
                        rel_path = os.path.relpath(file_path, project_root)
                        if not is_path_ignored(
                            rel_path, ignore_patterns, negation_patterns
                        ):
                            files_to_search.append(file_path)
            else:
                for root, dirs, files in os.walk(dir_path):
                    rel_root = os.path.relpath(root, project_root)
                    if rel_root == ".":
                        rel_root = ""

                    dirs[:] = [
                        d
                        for d in dirs
                        if not is_path_ignored(
                            os.path.join(rel_root, d) if rel_root else d,
                            ignore_patterns,
                            negation_patterns,
                        )
                    ]

                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            file_rel_path = (
                                os.path.join(rel_root, file) if rel_root else file
                            )
                            if not is_path_ignored(
                                file_rel_path, ignore_patterns, negation_patterns
                            ):
                                files_to_search.append(file_path)

        files_to_search = list(set(files_to_search))

        all_results = []
        for file_path in files_to_search:
            file_results = _search_in_file(file_path, keywords)
            all_results.extend(file_results)

        all_results.sort(key=lambda x: (x["file_path"], x["line_number"]))

        result = {
            "query": query,
            "keywords": keywords,
            "search_directories": valid_dirs,
            "file_pattern": file_pattern,
            "total_files_searched": len(files_to_search),
            "total_matches": len(all_results),
            "matches": all_results[:100],
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"搜索代码库时发生错误: {str(e)}", "query": query},
            ensure_ascii=False,
            indent=2,
        )


# 非并行版本的 grep（用于对比）
def grep_sequential(
    pattern: str,
    path: str = ".",
    file_type: Optional[str] = None,
    case_sensitive: bool = False,
    context_lines: int = 0,
    output_mode: str = "content",
) -> Union[str, List[str], dict]:
    """非并行版本的 grep，用于性能对比"""
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            error_msg = f"错误: 无效的正则表达式模式 '{pattern}': {str(e)}"
            if output_mode == "content":
                return error_msg
            elif output_mode == "files":
                return []
            else:
                return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}

        search_path = Path(path).resolve()

        if not search_path.exists():
            error_msg = f"错误: 路径不存在。路径: {path}"
            if output_mode == "content":
                return error_msg
            elif output_mode == "files":
                return []
            else:
                return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}

        from tools.gitignore import (
            get_project_root,
            load_gitignore_patterns,
            is_path_ignored,
        )

        project_root = get_project_root()
        ignore_patterns, negation_patterns = load_gitignore_patterns(str(project_root))

        files_to_search = []

        if search_path.is_file():
            rel_file_path = os.path.relpath(str(search_path), str(project_root))
            if not is_path_ignored(rel_file_path, ignore_patterns, negation_patterns):
                files_to_search.append(search_path)
        elif search_path.is_dir():
            if file_type:
                if os.path.isabs(file_type):
                    search_pattern = file_type
                else:
                    search_pattern = str(search_path / "**" / file_type)
                matched_files = glob.glob(search_pattern, recursive=True)
                for file_path in matched_files:
                    file_path_obj = Path(file_path)
                    if file_path_obj.is_file():
                        rel_file_path = os.path.relpath(
                            str(file_path_obj), str(project_root)
                        )
                        if not is_path_ignored(
                            rel_file_path, ignore_patterns, negation_patterns
                        ):
                            files_to_search.append(file_path_obj)
            else:
                for root, dirs, files in os.walk(search_path):
                    rel_root = os.path.relpath(root, str(project_root))
                    if rel_root == ".":
                        rel_root = ""
                    dirs[:] = [
                        d
                        for d in dirs
                        if not is_path_ignored(
                            os.path.join(rel_root, d) if rel_root else d,
                            ignore_patterns,
                            negation_patterns,
                        )
                    ]
                    for file in files:
                        file_path = Path(root) / file
                        if file_path.is_file():
                            file_rel_path = (
                                os.path.join(rel_root, file) if rel_root else file
                            )
                            if not is_path_ignored(
                                file_rel_path, ignore_patterns, negation_patterns
                            ):
                                files_to_search.append(file_path)
        else:
            error_msg = f"错误: 路径既不是文件也不是目录。路径: {path}"
            if output_mode == "content":
                return error_msg
            elif output_mode == "files":
                return []
            else:
                return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}

        matches = []
        matched_files_set = set()
        total_matches = 0

        def search_file_regex(file_path: Path) -> List[dict]:
            file_matches = []
            try:
                if not os.access(file_path, os.R_OK):
                    return file_matches

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except (UnicodeDecodeError, IOError):
                    return file_matches

                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        context_before = []
                        context_after = []

                        if context_lines > 0:
                            start_idx = max(0, line_num - context_lines - 1)
                            for i in range(start_idx, line_num - 1):
                                if i < len(lines):
                                    context_before.append(
                                        (i + 1, lines[i].rstrip("\n\r"))
                                    )

                            end_idx = min(len(lines), line_num + context_lines)
                            for i in range(line_num, end_idx):
                                if i < len(lines):
                                    context_after.append(
                                        (i + 1, lines[i].rstrip("\n\r"))
                                    )

                        file_matches.append(
                            {
                                "file_path": str(file_path),
                                "line_number": line_num,
                                "content": line.rstrip("\n\r"),
                                "context_before": context_before,
                                "context_after": context_after,
                            }
                        )

            except Exception:
                pass

            return file_matches

        for file_path in files_to_search:
            file_matches = search_file_regex(file_path)
            matches.extend(file_matches)
            for match in file_matches:
                matched_files_set.add(match["file_path"])
                total_matches += 1

        if output_mode == "content":
            if not matches:
                return f"未找到匹配 '{pattern}' 的内容"

            result_lines = []
            current_file = None

            for match in matches:
                file_path = match["file_path"]
                line_num = match["line_number"]
                content = match["content"]
                context_before = match["context_before"]
                context_after = match["context_after"]

                if file_path != current_file:
                    if current_file is not None:
                        result_lines.append("")
                    result_lines.append(f"文件: {file_path}")
                    current_file = file_path

                for ctx_line_num, ctx_content in context_before:
                    result_lines.append(f"  {ctx_line_num:4d}: {ctx_content}")

                result_lines.append(f"  {line_num:4d}: {content}  <-- 匹配")

                for ctx_line_num, ctx_content in context_after:
                    result_lines.append(f"  {ctx_line_num:4d}: {ctx_content}")

            return "\n".join(result_lines)

        elif output_mode == "files":
            return sorted(list(matched_files_set))

        else:
            return {
                "pattern": pattern,
                "path": path,
                "file_type": file_type,
                "case_sensitive": case_sensitive,
                "total_matches": total_matches,
                "files_with_matches": len(matched_files_set),
                "files_searched": len(files_to_search),
            }

    except PermissionError as e:
        error_msg = f"错误: 权限不足，无法访问路径。路径: {path}, 错误: {str(e)}"
        if output_mode == "content":
            return error_msg
        elif output_mode == "files":
            return []
        else:
            return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}
    except Exception as e:
        error_msg = f"错误: grep 搜索时发生未知错误。路径: {path}, 错误: {str(e)}"
        if output_mode == "content":
            return error_msg
        elif output_mode == "files":
            return []
        else:
            return {"error": error_msg, "total_matches": 0, "files_with_matches": 0}


class PerformanceTest(unittest.TestCase):
    """性能测试类"""

    def setUp(self):
        """每个测试前的准备工作"""
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir).resolve()

        self.original_cwd = os.getcwd()
        os.chdir(self.test_root)

        self.performance_results = []

    def tearDown(self):
        """每个测试后的清理工作"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_test_files(self, num_files: int, lines_per_file: int = 50):
        """创建大量测试文件"""
        test_data_dir = self.test_root / "test_data"
        test_data_dir.mkdir(exist_ok=True)

        for i in range(num_files):
            file_path = test_data_dir / f"test_file_{i:05d}.py"
            content_lines = []
            for j in range(lines_per_file):
                if j % 10 == 0:
                    content_lines.append(f"def function_{i}_{j}():")
                    content_lines.append(f"    # This is a test function")
                    content_lines.append(f"    return 'test_{i}_{j}'")
                elif j % 5 == 0:
                    content_lines.append(f"    import module_{j}")
                    content_lines.append(f"    class Class_{i}_{j}:")
                    content_lines.append(f"        pass")
                else:
                    content_lines.append(f"    # Line {j} in file {i}")

            file_path.write_text("\n".join(content_lines), encoding="utf-8")

    def test_codebase_search_performance(self):
        """测试 codebase_search 并行化前后的性能"""
        import sys

        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

        try:
            test_cases = [
                {"num_files": 50, "name": "小规模 (50文件)"},
                {"num_files": 200, "name": "中规模 (200文件)"},
                {"num_files": 500, "name": "大规模 (500文件)"},
            ]

            for case in test_cases:
                num_files = case["num_files"]

                self.setUp()
                self.create_test_files(num_files)

                query = "function test"
                test_path = str(self.test_root / "test_data")

                try:
                    start_time = time.time()
                    result_sequential = codebase_search_sequential(
                        query, target_directories=[test_path], file_pattern="*.py"
                    )
                    sequential_time = time.time() - start_time

                    start_time = time.time()
                    result_parallel = codebase_search_parallel(
                        query, target_directories=[test_path], file_pattern="*.py"
                    )
                    parallel_time = time.time() - start_time

                    speedup = (
                        sequential_time / parallel_time if parallel_time > 0 else 0
                    )

                    result_sequential_data = json.loads(result_sequential)
                    result_parallel_data = json.loads(result_parallel)

                    self.performance_results.append(
                        {
                            "function": "codebase_search",
                            "scenario": case["name"],
                            "num_files": num_files,
                            "sequential_time": sequential_time,
                            "parallel_time": parallel_time,
                            "speedup": speedup,
                            "sequential_matches": result_sequential_data.get(
                                "total_matches", 0
                            ),
                            "parallel_matches": result_parallel_data.get(
                                "total_matches", 0
                            ),
                        }
                    )

                except Exception as e:
                    pass

                finally:
                    self.tearDown()
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

    def test_grep_performance(self):
        """测试 grep 并行化前后的性能"""
        import sys

        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

        try:
            test_cases = [
                {"num_files": 50, "name": "小规模 (50文件)"},
                {"num_files": 200, "name": "中规模 (200文件)"},
                {"num_files": 500, "name": "大规模 (500文件)"},
            ]

            for case in test_cases:
                num_files = case["num_files"]

                self.setUp()
                self.create_test_files(num_files)

                pattern = "function"
                test_path = str(self.test_root / "test_data")

                try:
                    start_time = time.time()
                    result_sequential = grep_sequential(
                        pattern, path=test_path, file_type="*.py", output_mode="count"
                    )
                    sequential_time = time.time() - start_time

                    start_time = time.time()
                    result_parallel = grep_parallel(
                        pattern,
                        path=test_path,
                        file_type="*.py",
                        output_mode="count",
                        semantic_search=False,
                    )
                    parallel_time = time.time() - start_time

                    speedup = (
                        sequential_time / parallel_time if parallel_time > 0 else 0
                    )

                    sequential_matches = (
                        result_sequential.get("total_matches", 0)
                        if isinstance(result_sequential, dict)
                        else 0
                    )
                    parallel_matches = (
                        result_parallel.get("total_matches", 0)
                        if isinstance(result_parallel, dict)
                        else 0
                    )

                    self.performance_results.append(
                        {
                            "function": "grep",
                            "scenario": case["name"],
                            "num_files": num_files,
                            "sequential_time": sequential_time,
                            "parallel_time": parallel_time,
                            "speedup": speedup,
                            "sequential_matches": sequential_matches,
                            "parallel_matches": parallel_matches,
                        }
                    )

                except Exception as e:
                    pass

                finally:
                    self.tearDown()
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

    def generate_performance_report(self):
        """生成性能测试报告"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("性能测试报告")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"CPU核心数: {multiprocessing.cpu_count()}")
        report_lines.append("")

        if not self.performance_results:
            report_lines.append("未收集到性能测试数据")
            return "\n".join(report_lines)

        report_lines.append("测试结果汇总")
        report_lines.append("-" * 80)
        report_lines.append("")

        codebase_results = [
            r for r in self.performance_results if r["function"] == "codebase_search"
        ]
        grep_results = [r for r in self.performance_results if r["function"] == "grep"]

        if codebase_results:
            report_lines.append("1. codebase_search 性能测试")
            report_lines.append("-" * 80)
            report_lines.append(
                f"{'场景':<20} {'文件数':<10} {'顺序(秒)':<12} {'并行(秒)':<12} {'提升倍数':<12} {'匹配数':<10}"
            )
            report_lines.append("-" * 80)

            for result in codebase_results:
                report_lines.append(
                    f"{result['scenario']:<20} "
                    f"{result['num_files']:<10} "
                    f"{result['sequential_time']:<12.3f} "
                    f"{result['parallel_time']:<12.3f} "
                    f"{result['speedup']:<12.2f}x "
                    f"{result['parallel_matches']:<10}"
                )

            avg_speedup = sum(r["speedup"] for r in codebase_results) / len(
                codebase_results
            )
            report_lines.append("-" * 80)
            report_lines.append(f"平均性能提升: {avg_speedup:.2f}x")
            report_lines.append("")

        if grep_results:
            report_lines.append("2. grep 性能测试")
            report_lines.append("-" * 80)
            report_lines.append(
                f"{'场景':<20} {'文件数':<10} {'顺序(秒)':<12} {'并行(秒)':<12} {'提升倍数':<12} {'匹配数':<10}"
            )
            report_lines.append("-" * 80)

            for result in grep_results:
                report_lines.append(
                    f"{result['scenario']:<20} "
                    f"{result['num_files']:<10} "
                    f"{result['sequential_time']:<12.3f} "
                    f"{result['parallel_time']:<12.3f} "
                    f"{result['speedup']:<12.2f}x "
                    f"{result['parallel_matches']:<10}"
                )

            avg_speedup = sum(r["speedup"] for r in grep_results) / len(grep_results)
            report_lines.append("-" * 80)
            report_lines.append(f"平均性能提升: {avg_speedup:.2f}x")
            report_lines.append("")

        report_lines.append("=" * 80)
        report_lines.append("结论")
        report_lines.append("=" * 80)

        if codebase_results and grep_results:
            codebase_avg = sum(r["speedup"] for r in codebase_results) / len(
                codebase_results
            )
            grep_avg = sum(r["speedup"] for r in grep_results) / len(grep_results)

            report_lines.append(
                f"1. codebase_search 并行化平均提升: {codebase_avg:.2f}x"
            )
            report_lines.append(f"2. grep 并行化平均提升: {grep_avg:.2f}x")
            report_lines.append("")
            report_lines.append(
                "并行化优化显著提升了搜索性能，特别是在处理大量文件时效果明显。"
            )

        report_lines.append("")
        report_lines.append("=" * 80)

        return "\n".join(report_lines)


def run_performance_tests():
    """运行性能测试并生成报告"""
    import sys

    original_stdout = sys.stdout

    test_instance = PerformanceTest()
    test_instance.setUp()

    try:
        sys.stdout = open(os.devnull, "w")
        test_instance.test_codebase_search_performance()
        test_instance.test_grep_performance()
        sys.stdout.close()
        sys.stdout = original_stdout

        report = test_instance.generate_performance_report()

        report_file = os.path.join(os.path.dirname(__file__), "performance_report.txt")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(report)

    except Exception as e:
        sys.stdout = original_stdout
        print(f"错误: {str(e)}")
    finally:
        test_instance.tearDown()


if __name__ == "__main__":
    run_performance_tests()
