from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import os
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

# Type ignore is necessary because faiss lacks proper stubs
# See: https://github.com/facebookresearch/faiss/issues/1974
import faiss  # type: ignore

# mypy: disable-error-code="import-untyped"


class SearchResult:
    """搜索结果"""

    def __init__(
        self,
        file_path: str,
        line_number: int,
        content: str,
        similarity_score: float,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ):
        self.file_path = file_path
        self.line_number = line_number
        self.content = content
        self.similarity_score = similarity_score
        self.context_before = context_before or []
        self.context_after = context_after or []


class SemanticSearchEngine:
    """语义搜索引擎"""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: str = ".semantic_cache",
    ):
        self.model = SentenceTransformer(model_name)
        self.vector_store = faiss.IndexFlatL2(384)  # 直接初始化，避免 mypy 报错
        self.document_store: dict = (
            {}
        )  # 存储 (file_path, line_num) -> embedding_index 的映射
        self.cache_dir = cache_dir
        self.embedding_dim = 384  # all-MiniLM-L6-v2 的输出维度
        self._lock = threading.Lock()  # 用于保护共享资源的线程锁

        # 创建缓存目录
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        # 不再调用 _init_faiss_index，因为已直接初始化
        # self._init_faiss_index()
        # assert self.vector_store is not None, "FAISS vector store failed to initialize"

    def _init_faiss_index(self):
        """初始化 FAISS 向量索引"""
        self.vector_store = faiss.IndexFlatL2(self.embedding_dim)

    def _get_file_cache_path(self, file_path: str) -> str:
        """获取文件的缓存路径"""
        # 使用文件路径的哈希作为缓存文件名
        import hashlib

        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{file_hash}.npy")

    def _load_cached_embeddings(self, file_path: str) -> Optional[np.ndarray]:
        """从缓存加载文件的 embeddings"""
        cache_path = self._get_file_cache_path(file_path)
        if os.path.exists(cache_path):
            try:
                return np.load(cache_path)
            except Exception as e:
                logging.error(f"加载缓存失败 {cache_path}: {e}")
                return None
        return None

    def _save_embeddings_to_cache(self, file_path: str, embeddings: np.ndarray):
        """将 embeddings 保存到缓存"""
        cache_path = self._get_file_cache_path(file_path)
        try:
            np.save(cache_path, embeddings)
        except Exception as e:
            logging.error(f"保存缓存失败 {cache_path}: {e}")

    def _embed_lines(self, lines: List[str]) -> np.ndarray:
        """将多行文本转换为 embeddings"""
        # 过滤空行
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if not non_empty_lines:
            return np.array([]).reshape(0, self.embedding_dim)

        # 使用模型生成 embeddings
        embeddings = self.model.encode(non_empty_lines, convert_to_numpy=True)
        return embeddings

    def _prepare_file_data(self, file_path: str) -> Optional[Tuple[str, List[str], np.ndarray, List[int]]]:
        """准备文件数据：读取文件内容，检查缓存，返回文件路径、行内容、embeddings和有效行索引"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return None

            # 尝试从缓存加载
            cached_embeddings = None
            try:
                cached_embeddings = self._load_cached_embeddings(file_path)
            except IOError as e:
                logging.error(f"读取缓存文件IO错误: {file_path}, 错误: {e}")
            except Exception as e:
                logging.error(f"读取缓存文件失败: {file_path}, 错误: {e}")

            # 读取文件内容
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except IOError as e:
                logger.error(f"读取文件失败 {file_path}: {e}")
                return None

            # 过滤有效行索引
            valid_indices = [i for i, line in enumerate(lines) if line.strip()]
            
            # 检查缓存是否有效（缓存embeddings数量应该等于有效行数）
            if cached_embeddings is not None and len(cached_embeddings) == len(valid_indices):
                embeddings = cached_embeddings
            else:
                embeddings = None
            
            return (file_path, lines, embeddings, valid_indices)

        except Exception as e:
            logging.error(f"准备文件数据失败 {file_path}: {e}")
            return None

    def _index_single_file(self, file_path: str):
        """索引单个文件内容（线程安全）- 保留用于向后兼容"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return

            # 检查是否已索引（需要线程安全检查）
            with self._lock:
                # 检查文件是否已索引（通过检查document_store中是否有该文件的条目）
                file_already_indexed = any(
                    stored_file_path == file_path
                    for stored_file_path, _ in self.document_store.keys()
                )
                if file_already_indexed:
                    return

            # 尝试从缓存加载
            try:
                cached_embeddings = self._load_cached_embeddings(file_path)
            except IOError as e:
                logging.error(f"读取缓存文件IO错误: {file_path}, 错误: {e}")
                cached_embeddings = None
            except Exception as e:
                logging.error(f"读取缓存文件失败: {file_path}, 错误: {e}")
                cached_embeddings = None

            lines = []
            embeddings = np.array([]).reshape(0, self.embedding_dim)

            # 读取文件内容
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except IOError as e:
                logger.error(f"读取文件失败 {file_path}: {e}")
                return

            if cached_embeddings is not None and len(cached_embeddings) == len(lines):
                # 缓存有效，直接使用
                embeddings = cached_embeddings
            else:
                # 生成新的 embeddings
                embeddings = self._embed_lines([line.strip() for line in lines])
                # 保存到缓存
                self._save_embeddings_to_cache(file_path, embeddings)

            # 过滤掉空的 embedding（对应空行）
            valid_indices = [i for i, line in enumerate(lines) if line.strip()]
            if len(valid_indices) != len(embeddings):
                # 重新对齐
                min_len = min(len(valid_indices), len(embeddings))
                valid_indices = valid_indices[:min_len]
                embeddings = embeddings[:min_len]

            # 添加到 FAISS 索引（需要线程安全）
            if len(embeddings) > 0:
                with self._lock:
                    # 再次检查是否已索引（防止并发重复索引）
                    file_already_indexed = any(
                        stored_file_path == file_path
                        for stored_file_path, _ in self.document_store.keys()
                    )
                    if file_already_indexed:
                        return

                    self.vector_store.add(embeddings.astype("float32"))

                    # 更新 document_store 映射
                    start_idx = self.vector_store.ntotal - len(embeddings)
                    for i, line_idx in enumerate(valid_indices):
                        global_idx = start_idx + i
                        self.document_store[(file_path, line_idx + 1)] = (
                            global_idx  # line_number 从 1 开始
                        )

        except Exception as e:
            logging.error(f"索引文件失败 {file_path}: {e}")

    def index_files(self, file_paths: List[str], max_workers: Optional[int] = None):
        """索引文件内容（并行处理，批量生成Embeddings和批量添加到FAISS索引）"""
        if not file_paths:
            return

        # 过滤已索引的文件
        files_to_index = []
        with self._lock:
            indexed_files = set(
                stored_file_path for stored_file_path, _ in self.document_store.keys()
            )
            files_to_index = [fp for fp in file_paths if fp not in indexed_files]

        if not files_to_index:
            return

        # 设置线程池大小
        if max_workers is None:
            max_workers = min(len(files_to_index), multiprocessing.cpu_count() * 4, 64)
            max_workers = max(1, max_workers)

        # 第一阶段：并行读取所有文件内容和检查缓存
        file_data_list = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._prepare_file_data, file_path): file_path
                for file_path in files_to_index
            }

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    file_data = future.result()
                    if file_data is not None:
                        file_data_list.append(file_data)
                except IOError as e:
                    logging.error(f"处理文件IO错误 {file_path}: {e}")
                except Exception as e:
                    logging.error(f"处理文件失败 {file_path}: {e}")

        if not file_data_list:
            return

        # 第二阶段：批量生成Embeddings
        all_lines_to_embed = []
        line_to_file_map = []
        file_data_with_embeddings = []
        file_lines_map = {}  # 存储每个文件对应的lines

        for file_path, lines, cached_embeddings, valid_indices in file_data_list:
            file_lines_map[file_path] = lines
            if cached_embeddings is not None:
                # 使用缓存的embeddings
                file_data_with_embeddings.append(
                    (file_path, lines, cached_embeddings, valid_indices)
                )
            else:
                # 需要生成新的embeddings
                for line_idx in valid_indices:
                    all_lines_to_embed.append(lines[line_idx].strip())
                    line_to_file_map.append((file_path, line_idx))

        # 批量生成embeddings
        if all_lines_to_embed:
            try:
                batch_size = 32
                all_embeddings = self.model.encode(
                    all_lines_to_embed,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )

                # 将embeddings分组到对应的文件
                embedding_idx = 0
                current_file = None
                current_file_embeddings = []
                current_valid_indices = []

                for file_path, line_idx in line_to_file_map:
                    if file_path != current_file:
                        # 保存前一个文件的数据
                        if current_file is not None and current_file_embeddings:
                            file_data_with_embeddings.append(
                                (
                                    current_file,
                                    file_lines_map[current_file],
                                    np.array(current_file_embeddings),
                                    current_valid_indices,
                                )
                            )
                        # 开始新文件
                        current_file = file_path
                        current_file_embeddings = []
                        current_valid_indices = []

                    current_file_embeddings.append(all_embeddings[embedding_idx])
                    current_valid_indices.append(line_idx)
                    embedding_idx += 1

                # 保存最后一个文件的数据
                if current_file is not None and current_file_embeddings:
                    file_data_with_embeddings.append(
                        (
                            current_file,
                            file_lines_map[current_file],
                            np.array(current_file_embeddings),
                            current_valid_indices,
                        )
                    )

            except Exception as e:
                logging.error(f"批量生成embeddings失败: {e}")
                return

        # 第三阶段：批量添加到FAISS索引并更新缓存
        with self._lock:
            # 再次检查已索引的文件（防止并发重复索引）
            indexed_files = set(
                stored_file_path for stored_file_path, _ in self.document_store.keys()
            )

            all_embeddings_to_add = []
            all_mappings = []

            for file_path, lines, embeddings, valid_indices in file_data_with_embeddings:
                # 检查是否已索引
                if file_path in indexed_files:
                    continue

                # 对齐embeddings和valid_indices
                if len(valid_indices) != len(embeddings):
                    min_len = min(len(valid_indices), len(embeddings))
                    valid_indices = valid_indices[:min_len]
                    embeddings = embeddings[:min_len]

                if len(embeddings) > 0:
                    all_embeddings_to_add.append(embeddings.astype("float32"))
                    all_mappings.append((file_path, valid_indices))

                    # 保存到缓存（如果是从批量生成的）
                    if file_path not in [
                        fd[0] for fd in file_data_list if fd[2] is not None
                    ]:
                        try:
                            self._save_embeddings_to_cache(file_path, embeddings)
                        except Exception as e:
                            logging.error(f"保存缓存失败 {file_path}: {e}")

            # 批量添加到FAISS索引
            if all_embeddings_to_add:
                try:
                    # 合并所有embeddings
                    combined_embeddings = np.vstack(all_embeddings_to_add)
                    start_idx = self.vector_store.ntotal
                    self.vector_store.add(combined_embeddings)

                    # 更新document_store映射
                    current_idx = start_idx
                    for file_path, valid_indices in all_mappings:
                        for line_idx in valid_indices:
                            self.document_store[(file_path, line_idx + 1)] = (
                                current_idx  # line_number 从 1 开始
                            )
                            current_idx += 1

                except Exception as e:
                    logging.error(f"批量添加到FAISS索引失败: {e}")

    def _read_file_content(self, file_path: str) -> Optional[List[str]]:
        """读取文件内容的辅助函数（用于并行读取）"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.readlines()
        except Exception as e:
            logging.error(f"读取搜索结果文件失败: {file_path}, 错误: {e}")
            return None

    def search(
        self, query: str, top_k: int = 10, similarity_threshold: float = 0.3
    ) -> List[SearchResult]:
        """语义搜索"""
        if self.vector_store is None or self.vector_store.ntotal == 0:
            return []

        # 查询向量化
        query_embedding = self.model.encode([query], convert_to_numpy=True).astype(
            "float32"
        )

        # 执行相似度搜索
        distances, indices = self.vector_store.search(
            query_embedding, top_k * 2
        )  # 搜索更多结果用于过滤

        # 收集需要读取的文件路径和对应的索引信息
        file_read_tasks = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # 无效索引
                continue

            # 根据距离计算相似度分数（转换为 0-1 范围）
            # 使用余弦相似度：sim = 1 - d^2/2
            similarity = 1 - (dist**2) / 2

            if similarity < similarity_threshold:
                continue  # 低于阈值，跳过

            # 查找对应的文件和行号
            for (file_path, line_num), stored_idx in self.document_store.items():
                if stored_idx == idx:
                    file_read_tasks.append((file_path, line_num, similarity, idx))
                    break

        if not file_read_tasks:
            return []

        # 收集需要读取的唯一文件路径
        unique_files = list(set(task[0] for task in file_read_tasks))

        # 使用ThreadPoolExecutor并行读取文件
        file_contents_cache = {}
        max_workers = min(len(unique_files), multiprocessing.cpu_count() * 2, 32)
        max_workers = max(1, max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self._read_file_content, file_path): file_path
                for file_path in unique_files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    lines = future.result()
                    if lines is not None:
                        file_contents_cache[file_path] = lines
                except Exception as e:
                    logging.error(f"处理文件失败 {file_path}: {e}")

        # 处理搜索结果
        results = []
        added_count = 0

        for file_path, line_num, similarity, idx in file_read_tasks:
            if file_path not in file_contents_cache:
                continue

            lines = file_contents_cache[file_path]
            if 0 <= line_num - 1 < len(lines):
                content = lines[line_num - 1].rstrip("\n\r")

                # 获取上下文
                context_before = []
                context_after = []
                for i in range(max(0, line_num - 6), line_num - 1):  # 前 5 行
                    if i < len(lines):
                        context_before.append(lines[i].rstrip("\n\r"))
                for i in range(line_num, min(len(lines), line_num + 5)):  # 后 5 行
                    if i < len(lines):
                        context_after.append(lines[i].rstrip("\n\r"))

                result = SearchResult(
                    file_path=file_path,
                    line_number=line_num,
                    content=content,
                    similarity_score=similarity,
                    context_before=context_before,
                    context_after=context_after,
                )
                results.append(result)
                added_count += 1

            if added_count >= top_k:
                break

        return results
