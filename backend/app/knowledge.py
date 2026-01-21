"""
知识库表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Index
from sqlalchemy.sql import func
from app.db.session import Base


class Knowledge(Base):
    """知识库表"""
    __tablename__ = "rag_knowledge"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="知识库ID")
    user_id = Column(BigInteger, nullable=False, index=True, comment="所属用户ID")
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(String(500), nullable=True, comment="描述")
    avatar = Column(String(255), nullable=True, comment="知识库图标")
    embed_llm_id = Column(BigInteger, nullable=False, comment="使用的Embedding模型ID")
    vector_collection_name = Column(String(100), nullable=False, comment="向量数据库集合名称")
    
    # 向量化配置
    chunk_size = Column(Integer, default=500, comment="切片大小")
    chunk_overlap = Column(Integer, default=50, comment="切片重叠大小")
    
    # 统计信息
    document_count = Column(Integer, default=0, comment="文档数量")
    total_chunks = Column(Integer, default=0, comment="总切片数")
    
    status = Column(Integer, default=1, comment="状态：0-禁用，1-启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = (
        Index('idx_user', 'user_id'),
    )
    
    def __repr__(self):
        return f"<Knowledge(id={self.id}, name={self.name}, user_id={self.user_id})>"
