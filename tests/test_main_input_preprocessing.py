import unittest
from utils.path_parser import process_at_paths


class TestMainInputPreprocessing(unittest.TestCase):

    def test_simple_file_reference(self):
        """测试简单文件引用替换"""
        input_text = "请查看 @data/todos.json 的内容"
        result = process_at_paths(input_text)

        self.assertIn("--- BEGIN FILE: data/todos.json ---", result)
        self.assertIn("--- END FILE ---", result)
        # 确保原始 @path 被替换
        self.assertNotIn("@data/todos.json", result)

    def test_quoted_path(self):
        """测试引号包围的路径"""
        input_text = '分析 @"src/main module.py" 的代码'
        result = process_at_paths(input_text)

        self.assertIn(
            "--- BEGIN FILE: src/main module.py ---",
            result,
            "引号包裹的路径未被正确替换",
        )
        self.assertIn("--- END FILE ---", result)
        self.assertNotIn('@"src/main module.py"', result)

    def test_multiple_references(self):
        """测试多个路径引用"""
        input_text = "比较 @file1.txt 和 @file2.txt 的内容"
        result = process_at_paths(input_text)

        self.assertIn("--- BEGIN FILE: file1.txt ---", result, "第一个文件引用未被替换")
        self.assertIn("--- BEGIN FILE: file2.txt ---", result, "第二个文件引用未被替换")
        self.assertIn("--- BEGIN FILE: file2.txt ---", result)
        self.assertIn("--- END FILE ---", result)
        self.assertNotIn("@file1.txt", result)
        self.assertNotIn("@file2.txt", result)

    def test_nonexistent_path(self):
        """测试不存在的路径：应保留原样"""
        input_text = "打开 @nonexistent.txt 文件"
        original = input_text
        result = process_at_paths(input_text)

        # 不存在的路径不应被替换
        self.assertEqual(result, original)

    def test_directory_reference(self):
        """测试目录引用"""
        input_text = "列出 @my_folder/ 的内容"
        result = process_at_paths(input_text)

        self.assertIn(
            "--- BEGIN DIRECTORY: my_folder/ ---", result, "目录引用未被正确替换"
        )
        self.assertIn("--- END DIRECTORY ---", result)
        self.assertNotIn("@my_folder/", result)

    def test_malicious_paths(self):
        """测试恶意路径（如 ../）应在 validate_and_classify_path 中被拒绝"""
        # 假设 validate_and_classify_path 已实现安全检查
        input_text = "访问 @../config.json"
        result = process_at_paths(input_text)

        # 恶意路径不应被替换
        self.assertEqual(result, input_text)

    def test_empty_input(self):
        """测试空输入"""
        result = process_at_paths("")
        self.assertEqual(result, "")

    def test_none_input(self):
        """测试 None 输入"""
        result = process_at_paths(None)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
