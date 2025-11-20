from typing import List, Optional, Union, Dict, Iterator, Set
import os
import glob
from pathlib import Path
from collections import deque
import numpy as np

# 从tools文件夹导入semantic_search
from utils.semantic_search import SemanticSearchEngine, SearchResult

# 导入gitignore支持
from tools.gitignore import get_project_root, load_gitignore_patterns, is_path_ignored

# 定义需要排除的二进制文件扩展名
BINARY_FILE_EXTENSIONS: Set[str] = {
    # 图片文件
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff', '.tif',
    '.psd', '.ai', '.eps', '.raw', '.cr2', '.nef', '.orf', '.sr2',
    # 视频文件
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.mpg', '.mpeg',
    # 音频文件
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus',
    # Office文档
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',
    # PDF文件
    '.pdf',
    # 压缩文件
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.cab',
    # 可执行文件
    '.exe', '.dll', '.so', '.dylib', '.bin', '.app',
    # 数据库文件
    '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
    # 其他二进制文件
    '.iso', '.img', '.dmg', '.vmdk', '.ova',
    # 字体文件
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    # 其他
    '.pyc', '.pyo', '.pyd', '.class', '.jar', '.war', '.ear',
    # NumPy 数组文件
    '.npy', '.npz',
}

# 定义常见的文本文件扩展名（这些文件应该被包含）
TEXT_FILE_EXTENSIONS: Set[str] = {
    '.txt', '.md', '.rst', '.log', '.csv', '.json', '.xml', '.html', '.htm', '.css',
    '.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.properties',
    '.sql', '.r', '.m', '.pl', '.pm', '.lua', '.vim', '.el',
    '.dockerfile', '.makefile', '.cmake', '.gradle', '.sbt',
    '.vue', '.svelte', '.dart', '.elm', '.ex', '.exs', '.erl', '.hrl',
    '.fs', '.fsx', '.ml', '.mli', '.hs', '.lhs',
    '.tex', '.bib', '.sty', '.cls',
    '.proto', '.thrift', '.graphql', '.gql',
    '.lock', '.sum', '.mod', '.go.sum', '.go.mod',
}


def is_binary_file(file_path: Union[str, Path]) -> bool:
    """
    判断文件是否为二进制文件
    
    判断方法：
    1. 检查文件扩展名
    2. 如果扩展名不在已知列表中，读取文件前几个字节判断
    
    Args:
        file_path: 文件路径
        
    Returns:
        True 如果是二进制文件，False 如果是文本文件
    """
    file_path_obj = Path(file_path)
    
    # 获取文件扩展名（小写）
    ext = file_path_obj.suffix.lower()
    
    # 如果扩展名在二进制文件列表中，直接返回True
    if ext in BINARY_FILE_EXTENSIONS:
        return True
    
    # 如果扩展名在文本文件列表中，直接返回False
    if ext in TEXT_FILE_EXTENSIONS:
        return False
    
    # 如果没有扩展名或扩展名未知，尝试读取文件内容判断
    try:
        if not file_path_obj.exists() or not file_path_obj.is_file():
            return False
        
        # 读取文件前512字节来判断
        with open(file_path_obj, 'rb') as f:
            chunk = f.read(512)
            if not chunk:
                return False
            
            # 检查是否包含空字节（二进制文件的特征）
            if b'\x00' in chunk:
                return True
            
            # 检查是否大部分是可打印字符或常见空白字符
            # 如果超过30%的字节不是可打印字符，可能是二进制文件
            non_printable = sum(1 for byte in chunk if byte < 32 and byte not in [9, 10, 13])
            if len(chunk) > 0 and non_printable / len(chunk) > 0.3:
                return True
            
            # 尝试解码为UTF-8，如果失败可能是二进制文件
            try:
                chunk.decode('utf-8')
            except UnicodeDecodeError:
                return True
                
    except (IOError, PermissionError, OSError):
        # 如果无法读取，保守地假设是二进制文件
        return True
    
    return False


def collect_files(path: str, file_type: Optional[str] = None) -> List[str]:
    """收集要搜索的文件列表（广度优先遍历）"""
    files_to_search = []

    # 解析搜索路径
    search_path = Path(path).resolve()

    # 检查路径是否存在
    if not search_path.exists():
        return files_to_search

    # 获取项目根目录和 .gitignore 模式
    project_root = get_project_root()
    ignore_patterns, negation_patterns = load_gitignore_patterns(str(project_root))

    if search_path.is_file():
        # 排除二进制文件
        if is_binary_file(search_path):
            return files_to_search
        
        # 如果是文件，检查是否被 .gitignore 忽略
        rel_file_path = os.path.relpath(str(search_path), str(project_root))
        if not is_path_ignored(rel_file_path, ignore_patterns, negation_patterns):
            if file_type:
                # 检查文件类型是否匹配
                if search_path.match(file_type):
                    files_to_search.append(str(search_path))
            else:
                files_to_search.append(str(search_path))
    elif search_path.is_dir():
        # 使用广度优先遍历（BFS）
        queue = deque([search_path])
        
        while queue:
            current_dir = queue.popleft()
            
            try:
                # 获取当前目录的相对路径
                rel_dir = os.path.relpath(str(current_dir), str(project_root))
                if rel_dir == ".":
                    rel_dir = ""
                
                # 读取目录内容
                entries = list(current_dir.iterdir())
                dirs_to_process = []
                files_to_process = []
                
                for entry in entries:
                    if entry.is_dir():
                        dirs_to_process.append(entry)
                    elif entry.is_file():
                        files_to_process.append(entry)
                
                # 使用 .gitignore 规则过滤目录
                for d in dirs_to_process:
                    dir_rel_path = os.path.join(rel_dir, d.name) if rel_dir else d.name
                    if not is_path_ignored(dir_rel_path, ignore_patterns, negation_patterns):
                        queue.append(d)
                
                # 处理文件
                for file_path in files_to_process:
                    # 排除二进制文件
                    if is_binary_file(file_path):
                        continue
                    
                    if file_type:
                        # 检查文件类型是否匹配
                        if not file_path.match(file_type):
                            continue
                    
                    # 检查是否被 .gitignore 忽略
                    file_rel_path = os.path.join(rel_dir, file_path.name) if rel_dir else file_path.name
                    if not is_path_ignored(file_rel_path, ignore_patterns, negation_patterns):
                        files_to_search.append(str(file_path))
                        
            except PermissionError:
                # 跳过无权限访问的目录
                continue
            except Exception as e:
                # 记录其他错误但继续处理
                import logging
                logging.warning(f"处理目录失败 {current_dir}: {e}")
                continue

    return files_to_search


def collect_files_by_level(path: str, file_type: Optional[str] = None) -> Iterator[List[str]]:
    """按层级收集文件（广度优先遍历，逐层返回）"""
    # 解析搜索路径
    search_path = Path(path).resolve()

    # 检查路径是否存在
    if not search_path.exists():
        return

    # 获取项目根目录和 .gitignore 模式
    project_root = get_project_root()
    ignore_patterns, negation_patterns = load_gitignore_patterns(str(project_root))

    if search_path.is_file():
        # 排除二进制文件
        if is_binary_file(search_path):
            return
        
        # 如果是文件，直接返回
        rel_file_path = os.path.relpath(str(search_path), str(project_root))
        if not is_path_ignored(rel_file_path, ignore_patterns, negation_patterns):
            if file_type:
                if search_path.match(file_type):
                    yield [str(search_path)]
            else:
                yield [str(search_path)]
        return
    
    # 广度优先遍历，按层级返回文件
    queue = deque([(search_path, 0)])  # (目录路径, 层级)
    current_level = 0
    current_level_files = []
    
    while queue:
        current_dir, level = queue.popleft()
        
        # 如果进入新层级，先返回上一层的文件
        if level > current_level:
            if current_level_files:
                yield current_level_files
            current_level_files = []
            current_level = level
        
        try:
            # 获取当前目录的相对路径
            rel_dir = os.path.relpath(str(current_dir), str(project_root))
            if rel_dir == ".":
                rel_dir = ""
            
            # 读取目录内容
            entries = list(current_dir.iterdir())
            dirs_to_process = []
            files_to_process = []
            
            for entry in entries:
                if entry.is_dir():
                    dirs_to_process.append(entry)
                elif entry.is_file():
                    files_to_process.append(entry)
            
            # 使用 .gitignore 规则过滤目录，添加到队列
            for d in dirs_to_process:
                dir_rel_path = os.path.join(rel_dir, d.name) if rel_dir else d.name
                if not is_path_ignored(dir_rel_path, ignore_patterns, negation_patterns):
                    queue.append((d, level + 1))
            
            # 处理文件
            for file_path in files_to_process:
                # 排除二进制文件
                if is_binary_file(file_path):
                    continue
                
                if file_type:
                    # 检查文件类型是否匹配
                    if not file_path.match(file_type):
                        continue
                
                # 检查是否被 .gitignore 忽略
                file_rel_path = os.path.join(rel_dir, file_path.name) if rel_dir else file_path.name
                if not is_path_ignored(file_rel_path, ignore_patterns, negation_patterns):
                    current_level_files.append(str(file_path))
                    
        except PermissionError:
            # 跳过无权限访问的目录
            continue
        except Exception as e:
            # 记录其他错误但继续处理
            import logging
            logging.warning(f"处理目录失败 {current_dir}: {e}")
            continue
    
    # 返回最后一层的文件
    if current_level_files:
        yield current_level_files


def format_semantic_results(
    results: List[SearchResult], output_mode: str = "content", context_lines: int = 0
) -> Union[str, List[str], Dict]:
    """根据output_mode格式化语义搜索结果"""
    if output_mode == "files":
        # 返回唯一文件列表
        files = list(set([result.file_path for result in results]))
        return sorted(files)

    elif output_mode == "count":
        # 返回统计信息
        total_matches = len(results)
        unique_files = set([result.file_path for result in results])
        return {
            "total_matches": total_matches,
            "files_with_matches": len(unique_files),
            "similarity_threshold": 0.3,  # 这里应该从参数获取
            "results_returned": total_matches,
        }

    else:  # content mode
        if not results:
            return "未找到匹配的内容"

        result_lines = []
        current_file = None

        for result in results:
            # 添加文件分隔符（如果新文件）
            if result.file_path != current_file:
                if current_file is not None:
                    result_lines.append("")
                result_lines.append(
                    f"文件: {result.file_path} (相似度: {result.similarity_score:.3f})"
                )
                current_file = result.file_path

            # 添加上下文（前面的行）
            if context_lines > 0 and result.context_before:
                start_idx = max(0, len(result.context_before) - context_lines)
                for ctx_line in result.context_before[start_idx:]:
                    result_lines.append(f"  {ctx_line}")

            # 添加匹配行（标记）
            result_lines.append(
                f"  {result.line_number}: {result.content}  <-- 匹配 (相似度: {result.similarity_score:.3f})"
            )

            # 添加上下文（后面的行）
            if context_lines > 0 and result.context_after:
                end_idx = min(len(result.context_after), context_lines)
                for ctx_line in result.context_after[:end_idx]:
                    result_lines.append(f"  {ctx_line}")

        return "\n".join(result_lines)


def get_search_engine() -> SemanticSearchEngine:
    """获取或创建全局搜索引擎实例（单例模式）"""
    if not hasattr(get_search_engine, "_instance"):
        get_search_engine._instance = SemanticSearchEngine()
    return get_search_engine._instance


def semantic_grep(
    query: str,
    path: str = ".",
    file_type: Optional[str] = None,
    context_lines: int = 0,
    output_mode: str = "content",
    similarity_threshold: float = 0.3,
    top_k: int = 50,
    early_stop: bool = True,
) -> Union[str, List[str], dict]:
    """
    语义搜索实现（广度优先，支持提前返回）
    
    Args:
        query: 搜索查询
        path: 搜索路径
        file_type: 文件类型过滤
        context_lines: 上下文行数
        output_mode: 输出模式
        similarity_threshold: 相似度阈值
        top_k: 返回的最大结果数
        early_stop: 是否在找到足够高质量结果后提前返回（默认True）
    """
    # 1. 初始化搜索引擎（单例模式）
    search_engine = get_search_engine()
    
    all_results = []
    best_similarity = 0.0
    
    # 2. 按层级索引和搜索（广度优先）
    for level_files in collect_files_by_level(path, file_type):
        if not level_files:
            continue
        
        # 索引当前层级的文件
        search_engine.index_files(level_files)
        
        # 在当前索引中搜索
        level_results = search_engine.search(
            query=query, 
            top_k=top_k * 2,  # 搜索更多结果用于评估
            similarity_threshold=similarity_threshold
        )
        
        if level_results:
            # 更新最佳相似度
            best_similarity = max(best_similarity, max(r.similarity_score for r in level_results))
            all_results.extend(level_results)
            
            # 如果启用提前返回，且找到高质量结果，则提前返回
            if early_stop:
                # 检查是否有足够的高质量结果（相似度 > threshold + 0.2）
                high_quality_count = sum(1 for r in level_results if r.similarity_score > similarity_threshold + 0.2)
                if high_quality_count >= top_k:
                    # 找到足够的高质量结果，提前返回
                    all_results = sorted(all_results, key=lambda x: x.similarity_score, reverse=True)[:top_k]
                    return format_semantic_results(all_results, output_mode, context_lines)
        
        # 如果已经找到足够的结果，也可以提前返回
        if len(all_results) >= top_k and early_stop:
            # 按相似度排序并取前top_k个
            all_results = sorted(all_results, key=lambda x: x.similarity_score, reverse=True)[:top_k]
            return format_semantic_results(all_results, output_mode, context_lines)
    
    # 3. 如果没有找到文件
    if not all_results:
        if output_mode == "content":
            return "未找到匹配的内容"
        elif output_mode == "files":
            return []
        else:  # count
            return {
                "total_matches": 0,
                "files_with_matches": 0,
                "error": "未找到匹配的内容",
            }
    
    # 4. 按相似度排序并取前top_k个
    all_results = sorted(all_results, key=lambda x: x.similarity_score, reverse=True)[:top_k]
    
    # 5. 根据output_mode格式化结果
    return format_semantic_results(all_results, output_mode, context_lines)
