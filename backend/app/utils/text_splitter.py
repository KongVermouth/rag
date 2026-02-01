"""
文本切片工具
自定义实现递归字符切分，移除LangChain依赖
"""
import re
from typing import List, Optional
from app.core.config import settings


class RecursiveCharacterTextSplitter:
    """
    递归字符文本切分器
    模仿 LangChain 的 RecursiveCharacterTextSplitter 实现
    """
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        length_function=len,
        is_separator_regex: bool = False
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        self.is_separator_regex = is_separator_regex

    def split_text(self, text: str) -> List[str]:
        """切分文本"""
        final_chunks = []
        
        # 获取合适的切分符
        separator = self.separators[-1]
        new_separators = []
        
        for i, sep in enumerate(self.separators):
            if self._is_separator_present(text, sep):
                separator = sep
                new_separators = self.separators[i + 1:]
                break
                
        # 使用切分符切分
        splits = self._split_text_with_separator(text, separator)
        
        # 此时 splits 是初步切分的结果，需要检查每一段是否过长
        good_splits = []
        
        for s in splits:
            if self.length_function(s) < self.chunk_size:
                good_splits.append(s)
            else:
                # 如果还有更细的切分符，递归切分
                if new_separators:
                    sub_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=new_separators,
                        length_function=self.length_function,
                        is_separator_regex=self.is_separator_regex
                    )
                    good_splits.extend(sub_splitter.split_text(s))
                else:
                    # 没有更细的切分符了，强行切分（这里简单处理，实际可以按字符强切）
                    # 考虑到最后是空字符串切分，应该已经按字符切了
                    good_splits.append(s)
                    
        # 合并小片段
        return self._merge_splits(good_splits, separator)

    def _is_separator_present(self, text: str, separator: str) -> bool:
        if self.is_separator_regex:
            return bool(re.search(separator, text))
        return separator in text

    def _split_text_with_separator(self, text: str, separator: str) -> List[str]:
        if self.is_separator_regex:
            # 保留分隔符
            splits = re.split(f"({separator})", text)
            # 重新组合：内容+分隔符
            # re.split 返回 [text, sep, text, sep, ...]
            # 我们希望结果是 [text+sep, text+sep, ...] 或者 [text, sep+text]
            # 这里简单处理：将分隔符附在前面一段的末尾（除了第一段）
            # 或者按照 Langchain 的逻辑，分隔符如果是 \n\n，通常作为连接符
            
            # 简化实现：直接 split，不保留分隔符（或者简单保留）
            # 为了更好的还原，我们采用 split 后再 join 的方式
            # 这里简单用 split，后续 merge 时再加回来
            
            # 实际上 Langchain 的实现比较复杂。
            # 我们这里简化：使用 split，不保留 separator 在 chunks 里，但在 merge 时使用 separator 连接
            return re.split(separator, text)
        else:
            if separator:
                return text.split(separator)
            else:
                return list(text)

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """合并切分好的片段"""
        final_chunks = []
        current_chunk = []
        current_length = 0
        
        separator_len = self.length_function(separator) if separator else 0
        
        for s in splits:
            if not s:
                continue
                
            s_len = self.length_function(s)
            
            # 如果当前块加上新片段超过大小，先保存当前块
            if current_length + s_len + (separator_len if current_length > 0 else 0) > self.chunk_size:
                if current_chunk:
                    doc = self._join_docs(current_chunk, separator)
                    final_chunks.append(doc)
                    
                    # 处理重叠：保留尾部
                    # 这是一个简化的重叠处理，可能不如 Langchain 精确
                    while current_length > self.chunk_overlap and current_chunk:
                        current_length -= self.length_function(current_chunk.pop(0)) + separator_len
                    
            current_chunk.append(s)
            current_length += s_len + (separator_len if current_length > 0 else 0)
            
        if current_chunk:
            final_chunks.append(self._join_docs(current_chunk, separator))
            
        return final_chunks

    def _join_docs(self, docs: List[str], separator: str) -> str:
        text = separator.join(docs)
        return text.strip()


class TextSplitter:
    """文本切片工具类"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        初始化文本切片器
        
        Args:
            chunk_size: 切片大小（字符数）
            chunk_overlap: 切片重叠大小（字符数）
        """
        self.chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
            length_function=len
        )
    
    def split_text(self, text: str) -> List[str]:
        """
        将文本切分为多个片段
        
        Args:
            text: 待切分的文本
        
        Returns:
            切片列表
        """
        chunks = self.splitter.split_text(text)
        return chunks
    
    def split_documents(self, text: str) -> List[dict]:
        """
        将文本切分为文档片段（包含元数据）
        
        Args:
            text: 待切分的文本
        
        Returns:
            包含内容和元数据的切片列表
        """
        chunks = self.split_text(text)
        
        documents = []
        for i, chunk in enumerate(chunks):
            documents.append({
                "chunk_index": i,
                "content": chunk,
                "char_count": len(chunk)
            })
        
        return documents


# 创建默认切片器实例
text_splitter = TextSplitter()
