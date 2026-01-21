"""
问答机器人表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Float, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class Robot(Base):
    """问答机器人配置表"""
    __tablename__ = "rag_robot"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="机器人ID")
    user_id = Column(BigInteger, nullable=False, index=True, comment="所属用户ID")
    name = Column(String(100), nullable=False, comment="机器人名称")
    avatar = Column(String(255), nullable=True, comment="机器人头像")
    chat_llm_id = Column(BigInteger, nullable=False, comment="使用的对话模型ID")
    description = Column(String(500), nullable=True, comment="机器人描述")
    
    # 提示词配置
    system_prompt = Column(Text, nullable=True, comment="系统提示词")
    welcome_msg = Column(String(500), nullable=True, comment="欢迎语")
    suggested_questions = Column(JSON, nullable=True, comment="推荐问题")
    
    # 检索配置 (RAG参数)
    similarity_threshold = Column(Float, default=0.6, comment="相似度阈值")
    top_k = Column(Integer, default=5, comment="召回切片数量")
    
    # 生成配置
    temperature = Column(Float, default=0.7, comment="生成温度")
    max_tokens = Column(Integer, default=2000, comment="最大生成Token数")
    
    status = Column(Integer, default=1, comment="状态: 0=下线, 1=上线")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = (
        Index('idx_user', 'user_id'),
    )
    
    def __repr__(self):
        return f"<Robot(id={self.id}, name={self.name}, user_id={self.user_id})>"
