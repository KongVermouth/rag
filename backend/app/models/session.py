"""
用户会话表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.session import Base


class Session(Base):
    """用户会话表"""
    __tablename__ = "rag_session"
    
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="会话ID")
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment="会话UUID")
    user_id = Column(BigInteger, nullable=False, index=True, comment="所属用户ID")
    robot_id = Column(BigInteger, nullable=False, index=True, comment="关联的机器人ID")
    
    # 会话元数据
    title = Column(String(200), nullable=True, comment="会话标题")
    summary = Column(String(500), nullable=True, comment="会话摘要")
    message_count = Column(Integer, nullable=False, default=0, comment="消息数量")
    
    # 会话状态
    status = Column(String(20), nullable=False, default="active", comment="状态: active, archived, deleted")
    is_pinned = Column(Integer, nullable=False, default=0, comment="是否置顶: 0=否, 1=是")
    
    # 时间戳
    last_message_at = Column(DateTime, nullable=True, comment="最后一条消息时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 额外元数据
    meta_data = Column(JSON, nullable=True, comment="扩展元数据")
    
    def __repr__(self):
        return f"<Session(id={self.id}, session_id={self.session_id}, user_id={self.user_id})>"
