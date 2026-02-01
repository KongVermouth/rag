"""
LLM模型表
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class LLM(Base):
    """大模型定义表"""
    __tablename__ = "rag_llm"
    
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="模型ID")
    user_id = Column(BigInteger, nullable=False, comment="创建者用户ID")
    name = Column(String(100), nullable=False, comment="模型显示名称")
    model_type = Column(String(20), nullable=False, comment="类型: chat(对话), embedding(向量化), rerank(重排)")
    provider = Column(String(50), nullable=False, comment="提供商: openai, azure, anthropic, qwen, local")
    model_name = Column(String(100), nullable=False, comment="模型标识")
    base_url = Column(String(255), nullable=True, comment="API Endpoint (非标准地址)")
    api_version = Column(String(50), nullable=True, comment="API版本")
    max_tokens = Column(Integer, default=4096, comment="最大上下文Token数")
    description = Column(String(1000), nullable=True, comment="模型描述")
    status = Column(Integer, default=1, comment="状态：0-禁用，1-启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<LLM(id={self.id}, name={self.name}, provider={self.provider}, model_name={self.model_name})>"
