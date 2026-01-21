"""
API Key表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Index
from sqlalchemy.sql import func
from app.db.session import Base


class APIKey(Base):
    """模型API Key管理表"""
    __tablename__ = "rag_apikey"
    
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="Key ID")
    user_id = Column(BigInteger, nullable=False, comment="创建者用户ID")
    llm_id = Column(BigInteger, nullable=False, index=True, comment="关联的模型ID")
    alias = Column(String(100), nullable=False, comment="Key别名/名称")
    api_key_encrypted = Column(Text, nullable=False, comment="加密后的API Key")
    description = Column(String(500), nullable=True, comment="密钥描述")
    status = Column(Integer, default=1, comment="状态: 0=禁用, 1=启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = (
        Index('idx_apikey_llm', 'llm_id'),
        Index('idx_apikey_user', 'user_id'),
    )
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, llm_id={self.llm_id}, alias={self.alias})>"
