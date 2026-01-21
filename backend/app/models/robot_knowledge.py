"""
机器人-知识库关联表模型
"""
from sqlalchemy import Column, BigInteger, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func
from app.db.session import Base


class RobotKnowledge(Base):
    """机器人知识库关联表"""
    __tablename__ = "rag_robot_knowledge"
    
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="ID")
    robot_id = Column(BigInteger, nullable=False, comment="机器人ID")
    knowledge_id = Column(BigInteger, nullable=False, comment="知识库ID")
    created_at = Column(DateTime, server_default=func.now(), comment="关联时间")
    
    __table_args__ = (
        UniqueConstraint('robot_id', 'knowledge_id', name='uk_robot_kb'),
        Index('idx_kb', 'knowledge_id'),
    )
    
    def __repr__(self):
        return f"<RobotKnowledge(robot_id={self.robot_id}, knowledge_id={self.knowledge_id})>"
