"""
文本切片工具
使用LangChain进行文本分割
"""
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.core.config import settings


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
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
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
