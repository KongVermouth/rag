"""
用户历史问答记录表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.session import Base


class ChatHistory(Base):
    """用户历史问答记录表"""
    __tablename__ = "rag_chat_history"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    session_id = Column(String(64), nullable=False, index=True, comment="所属会话UUID")
    message_id = Column(String(64), unique=True, nullable=False, index=True, comment="消息UUID")
    
    # 消息内容
    role = Column(String(20), nullable=False, comment="角色: user, assistant, system")
    content = Column(Text, nullable=False, comment="消息内容")
    
    # 关联信息（仅assistant角色）
    retrieved_contexts = Column(JSON, nullable=True, comment="检索到的上下文")
    referenced_doc_ids = Column(JSON, nullable=True, comment="引用的文档ID列表")
    
    # Token统计
    prompt_tokens = Column(Integer, nullable=False, default=0, comment="Prompt Token数")
    completion_tokens = Column(Integer, nullable=False, default=0, comment="回答Token数")
    total_tokens = Column(Integer, nullable=False, default=0, comment="总Token数")
    
    # 性能指标
    retrieval_time_ms = Column(Integer, nullable=False, default=0, comment="检索耗时(毫秒)")
    generation_time_ms = Column(Integer, nullable=False, default=0, comment="生成耗时(毫秒)")
    total_time_ms = Column(Integer, nullable=False, default=0, comment="总耗时(毫秒)")
    
    # 用户反馈
    feedback = Column(Integer, nullable=True, comment="用户反馈: 1=有用, -1=无用")
    feedback_comment = Column(String(500), nullable=True, comment="反馈评论")
    
    # 序号与时间
    sequence = Column(Integer, nullable=False, comment="消息在会话中的序号")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 额外元数据
    meta_data = Column(JSON, nullable=True, comment="扩展元数据")
    
    def __repr__(self):
        return f"<ChatHistory(id={self.id}, session_id={self.session_id}, role={self.role})>"
