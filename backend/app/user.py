"""
用户表模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class User(Base):
    """用户表"""
    __tablename__ = "rag_user"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(100), unique=True, nullable=False, index=True, comment="邮箱")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    avatar_url = Column(String(255), nullable=True, comment="头像地址")
    role = Column(String(20), nullable=False, default="user", comment="角色: admin, user")
    status = Column(Integer, nullable=False, default=1, comment="状态: 0=禁用, 1=正常")
    password_changed_at = Column(DateTime, nullable=True, comment="密码最后修改时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
