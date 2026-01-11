"""
文件存储工具
支持本地存储和OSS存储（预留接口）
"""
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional
from datetime import datetime
import uuid
from app.core.config import settings


class FileStorage:
    """文件存储工具类"""
    
    def __init__(self):
        self.base_path = Path(settings.FILE_STORAGE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_file(
        self,
        file: BinaryIO,
        original_filename: str,
        knowledge_id: int
    ) -> tuple[str, int]:
        """
        保存上传的文件
        
        Args:
            file: 文件对象
            original_filename: 原始文件名
            knowledge_id: 知识库ID
        
        Returns:
            (文件路径, 文件大小)
        """
        # 按日期和知识库组织目录
        date_path = datetime.now().strftime("%Y%m%d")
        storage_dir = self.base_path / str(knowledge_id) / date_path
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名：UUID + 原始扩展名
        file_ext = Path(original_filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = storage_dir / unique_filename
        
        # 保存文件
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file, f)
        
        # 获取文件大小
        file_size = file_path.stat().st_size
        
        # 返回相对路径
        relative_path = str(file_path.relative_to(self.base_path))
        
        return relative_path, file_size
    
    def get_file_path(self, relative_path: str) -> Path:
        """
        获取文件的绝对路径
        
        Args:
            relative_path: 相对路径
        
        Returns:
            绝对路径
        """
        return self.base_path / relative_path
    
    def delete_file(self, relative_path: str) -> bool:
        """
        删除文件
        
        Args:
            relative_path: 相对路径
        
        Returns:
            是否成功
        """
        file_path = self.get_file_path(relative_path)
        
        if file_path.exists():
            file_path.unlink()
            return True
        
        return False
    
    def delete_knowledge_files(self, knowledge_id: int) -> bool:
        """
        删除知识库的所有文件
        
        Args:
            knowledge_id: 知识库ID
        
        Returns:
            是否成功
        """
        kb_dir = self.base_path / str(knowledge_id)
        
        if kb_dir.exists():
            shutil.rmtree(kb_dir)
            return True
        
        return False
    
    def get_storage_stats(self) -> dict:
        """
        获取存储统计信息
        
        Returns:
            统计信息字典
        """
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                file_path = Path(root) / file
                total_size += file_path.stat().st_size
                file_count += 1
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "base_path": str(self.base_path)
        }


# 创建全局文件存储实例
file_storage = FileStorage()
