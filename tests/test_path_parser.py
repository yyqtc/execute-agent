import unittest
from utils.path_parser import (
    extract_paths_from_text,
    validate_and_classify_path,
    read_file_content,
    process_at_paths,
)
from pathlib import Path
import tempfile
import os


class TestPathParser(unittest.TestCase):

    def test_extract_paths_simple(self):
        """测试基本路径提取"""
        text = "查看这个文件 @data/todos.json 和那个 @utils/main.py"
        expected = ["data/todos.json", "utils/main.py"]
        result = extract_paths_from_text(text)
        self.assertEqual(result, expected)

    def test_extract_paths_with_spaces_in_quotes(self):
        """测试带空格的引号路径"""
        text = '处理 @"data/my documents/file.txt" 和 @"src/long path/module.py"'
        expected = ["data/my documents/file.txt", "src/long path/module.py"]
        result = extract_paths_from_text(text)
        self.assertEqual(result, expected)

    def test_extract_paths_mixed_quotes_and_normal(self):
        """测试混合引号和非引号路径"""
        text = '@normal.txt @"spaced file.txt" @another.txt'
        expected = ["normal.txt", "spaced file.txt", "another.txt"]
        result = extract_paths_from_text(text)
        self.assertEqual(result, expected)

    def test_extract_paths_multiple_ats(self):
        """测试多个 @ 符号"""
        text = "@@@three@@@"
        # 每个 @ 后都应尝试提取，但中间无内容
        result = extract_paths_from_text(text)
        # 实际行为：@后紧跟@或空白会被忽略
        self.assertEqual(len(result), 1)  # 提取到 'three'

    def test_extract_paths_no_at_symbol(self):
        """测试无 @ 符号"""
        text = "This has no at symbol"
        result = extract_paths_from_text(text)
        self.assertEqual(result, [])

    def test_extract_paths_leading_trailing_spaces(self):
        """测试路径前后空格"""
        text = "@   spaced_path.txt   and @  another  "
        expected = ["spaced_path.txt", "another"]
        result = extract_paths_from_text(text)
        self.assertEqual(result, expected)

    def test_extract_paths_empty_string(self):
        """测试空字符串"""
        result = extract_paths_from_text("")
        self.assertEqual(result, [])

    def test_extract_paths_none_input(self):
        """测试 None 输入"""
        result = extract_paths_from_text(None)
        self.assertEqual(result, [])

    def test_validate_existing_file(self):
        """测试验证存在的文件"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            temp_path = f.name

        try:
            success, path_type, error = validate_and_classify_path(temp_path)
            self.assertTrue(success)
            self.assertEqual(path_type, "file")
            self.assertIsNone(error)
        finally:
            os.unlink(temp_path)

    def test_validate_existing_directory(self):
        """测试验证存在的目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            success, path_type, error = validate_and_classify_path(temp_dir)
            self.assertTrue(success)
            self.assertEqual(path_type, "directory")
            self.assertIsNone(error)

    def test_validate_nonexistent_path(self):
        """测试验证不存在的路径"""
        success, path_type, error = validate_and_classify_path(
            "/path/that/does/not/exist/abc123.txt"
        )
        self.assertFalse(success)
        self.assertEqual(path_type, "invalid")
        self.assertIsNotNone(error)

    def test_read_valid_file(self):
        """测试读取有效文件"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            content = "Hello, 世界!\nThis is a test file."
            f.write(content)
            temp_path = f.name

        try:
            success, result = read_file_content(temp_path)
            self.assertTrue(success)
            self.assertEqual(result, content)
        finally:
            os.unlink(temp_path)

    def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""

        success, result = read_file_content("/path/that/does/not/exist.txt")
        self.assertFalse(success)
        self.assertIn("不是文件", result)  # 根据实际错误信息调整

    def test_process_at_paths_with_file(self):
        """测试处理包含文件路径的输入"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            temp_path = f.name

        try:
            input_text = f"请查看 @'{temp_path}' 的内容"
            result = process_at_paths(input_text)

            self.assertIn(f"--- BEGIN FILE: {temp_path} ---", result)
            self.assertIn("test content", result)
        finally:
            os.unlink(temp_path)

    def test_process_at_paths_with_directory(self):
        """测试处理包含目录路径的输入"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建一些测试文件
            Path(temp_dir, "file1.txt").write_text("content1")
            Path(temp_dir, "file2.py").write_text("print('hello')")

            input_text = f"列出 @'{temp_dir}' 的内容"
            result = process_at_paths(input_text)

            self.assertIn(f"--- BEGIN DIRECTORY: {temp_dir} ---", result)
            self.assertIn("[F] file1.txt", result)
            self.assertIn("[F] file2.py", result)

    def test_process_at_paths_nonexistent(self):
        """测试处理不存在的路径"""
        input_text = "打开 @/nonexistent/path.txt"
        result = process_at_paths(input_text)
        self.assertIn("路径 '/nonexistent/path.txt' 不存在", result)

    def test_process_at_paths_invalid_input(self):
        """测试无效输入"""
        result = process_at_paths(None)
        self.assertEqual(result, "请输入有效文本。")

        result = process_at_paths("")
        self.assertEqual(result, "请输入有效文本。")


if __name__ == "__main__":
    unittest.main()
