"""
文档表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class Document(Base):
    """文档表"""
    __tablename__ = "rag_document"
    
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="文档ID")
    knowledge_id = Column(BigInteger, nullable=False, index=True, comment="所属知识库ID")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径/OSS地址")
    file_extension = Column(String(20), nullable=False, comment="文件后缀")
    file_size = Column(BigInteger, default=0, comment="文件大小(字节)")
    mime_type = Column(String(100), nullable=True, comment="文件MIME类型")
    width = Column(Integer, nullable=True, comment="宽度(图片/视频)")
    height = Column(Integer, nullable=True, comment="高度(图片/视频)")
    
    # 处理状态
    status = Column(String(20), default="uploading", comment="状态: uploading, parsing, embedding, completed, failed")
    chunk_count = Column(Integer, default=0, comment="生成的切片数量")
    error_msg = Column(Text, nullable=True, comment="失败时的错误信息")
    
    meta_data = Column(JSON, nullable=True, comment="文档元数据")
    
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = (
        Index('idx_knowledge', 'knowledge_id'),
        Index('idx_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Document(id={self.id}, file_name={self.file_name}, status={self.status})>"
