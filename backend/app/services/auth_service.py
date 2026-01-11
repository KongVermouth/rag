"""
认证服务 - 用户注册、登录、Token生成
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, TokenResponse
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务类"""

    @staticmethod
    def register(db: Session, user_data: UserRegister) -> User:
        """
        用户注册
        
        Args:
            db: 数据库会话
            user_data: 注册数据
            
        Returns:
            User: 新创建的用户对象
            
        Raises:
            HTTPException: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        # 检查邮箱是否已存在
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )

        # 创建新用户
        try:
            new_user = User(
                username=user_data.username,
                email=user_data.email,
                password_hash=get_password_hash(user_data.password),
                role=user_data.role,  # 使用传入的角色，默认为"user"
                status=1,  # 默认启用
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"用户注册成功: {new_user.username} (ID: {new_user.id})")
            return new_user
        except IntegrityError as e:
            db.rollback()
            logger.error(f"用户注册失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用户注册失败，请稍后重试"
            )

    @staticmethod
    def login(db: Session, login_data: UserLogin) -> TokenResponse:
        """
        用户登录
        
        Args:
            db: 数据库会话
            login_data: 登录数据
            
        Returns:
            TokenResponse: 访问令牌
            
        Raises:
            HTTPException: 用户不存在、密码错误或账号被禁用
        """
        # 支持用户名或邮箱登录
        user = db.query(User).filter(
            (User.username == login_data.username) | (User.email == login_data.username)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        # 验证密码
        if not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        # 检查账号状态
        if user.status != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用，请联系管理员"
            )

        # 生成访问令牌
        expires_delta = timedelta(hours=settings.JWT_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": user.role},
            expires_delta=expires_delta
        )

        logger.info(f"用户登录成功: {user.username} (ID: {user.id})")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_EXPIRE_HOURS * 3600
        )

    @staticmethod
    def validate_token(db: Session, user_id: int) -> User:
        """
        验证Token并返回用户信息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            User: 用户对象
            
        Raises:
            HTTPException: 用户不存在或账号被禁用
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        if user.status != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )

        return user


# 全局认证服务实例
auth_service = AuthService()
