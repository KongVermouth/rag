"""
用户管理服务
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserUpdate, PasswordChange, UserListResponse, UserDetail
from app.core.security import verify_password, get_password_hash

logger = logging.getLogger(__name__)


class UserService:
    """用户管理服务类"""

    @staticmethod
    def _check_admin_permission(current_user: User) -> None:
        """
        检查用户是否为管理员
        
        Args:
            current_user: 当前用户
            
        Raises:
            HTTPException: 403 权限不足
        """
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员才能执行此操作"
            )

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """根据ID获取用户"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        return user

    @staticmethod
    def get_user_detail(db: Session, user_id: int, current_user: User) -> User:
        """
        获取用户详情（仅管理员可查看，且只能查看 user 级别用户）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            current_user: 当前操作用户（必须是管理员）
            
        Returns:
            User: 用户对象
            
        Raises:
            HTTPException: 403 权限不足或 404 用户不存在
        """
        # 权限校验：只有管理员可以查看用户详情
        UserService._check_admin_permission(current_user)
        
        user = UserService.get_user_by_id(db, user_id)
        
        # 只能查看 user 级别的用户，不能查看其他 admin
        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看其他管理员信息"
            )
        
        return user

    @staticmethod
    def get_users(
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None
    ) -> UserListResponse:
        """
        获取用户列表（仅管理员可查看，且只返回 role 为 user 的用户）
        
        Args:
            db: 数据库会话
            current_user: 当前操作用户（必须是管理员）
            skip: 跳过记录数
            limit: 返回记录数
            keyword: 搜索关键词（用户名或邮箱）
            
        Returns:
            UserListResponse: 用户列表响应
            
        Raises:
            HTTPException: 403 权限不足
        """
        # 权限校验：只有管理员可以查看用户列表
        UserService._check_admin_permission(current_user)
        
        # 只查询 role 为 user 的用户，不返回其他 admin
        query = db.query(User).filter(User.role == "user")

        # 关键词搜索
        if keyword:
            query = query.filter(
                (User.username.like(f"%{keyword}%")) |
                (User.email.like(f"%{keyword}%"))
            )

        total = query.count()
        users = query.offset(skip).limit(limit).all()

        return UserListResponse(
            total=total,
            items=[UserDetail.model_validate(user) for user in users]
        )

    @staticmethod
    def update_user(db: Session, user_id: int, user_data: UserUpdate, current_user: User) -> User:
        """
        更新用户信息（仅管理员可更新，且只能更新 user 级别用户）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            user_data: 更新数据
            current_user: 当前操作用户（必须是管理员）
            
        Returns:
            User: 更新后的用户对象
            
        Raises:
            HTTPException: 权限不足或用户不存在
        """
        # 权限检查：只有管理员可以更新用户信息
        UserService._check_admin_permission(current_user)

        user = UserService.get_user_by_id(db, user_id)
        
        # 只能更新 user 级别的用户，不能更新其他 admin
        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改其他管理员信息"
            )

        # 更新字段
        if user_data.email is not None:
            # 检查邮箱是否已被其他用户使用
            existing = db.query(User).filter(
                User.email == user_data.email,
                User.id != user_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被其他用户使用"
                )
            user.email = user_data.email

        # 管理员可以修改角色和状态
        if user_data.role is not None:
            # 校验 role 必须为 admin 或 user
            if user_data.role not in ("admin", "user"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="role 必须为 'admin' 或 'user'"
                )
            user.role = user_data.role
        if user_data.status is not None:
            # 校验 status 必须为 0 或 1
            if user_data.status not in (0, 1):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="status 必须为 0 或 1"
                )
            user.status = user_data.status

        user.updated_at = datetime.now()
        db.commit()
        db.refresh(user)

        logger.info(f"用户信息更新: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    def change_password(db: Session, current_user: User, password_data: PasswordChange) -> None:
        """
        修改密码（用户只能修改自己的密码）
        
        修改密码后当前 token 将失效，需要重新登录
        
        Args:
            db: 数据库会话
            current_user: 当前登录用户
            password_data: 密码修改数据
            
        Raises:
            HTTPException: 旧密码错误
        """
        # 验证旧密码
        if not verify_password(password_data.old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码错误"
            )

        # 更新密码和密码修改时间（使用 UTC 时间，与 JWT token 的 iat 保持一致）
        current_user.password_hash = get_password_hash(password_data.new_password)
        current_user.password_changed_at = datetime.now(timezone.utc)
        current_user.updated_at = datetime.now()
        db.commit()

        logger.info(f"用户修改密码: {current_user.username} (ID: {current_user.id})")

    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User) -> None:
        """
        删除用户
        
        权限规则：
        - 只有 admin 可以删除 user
        - admin 之间不能相互删除
        - user 之间也不能互相删除
        - 不能删除自己
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            current_user: 当前操作用户
            
        Raises:
            HTTPException: 权限不足或不能删除
        """
        # 不能删除自己
        if current_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除自己的账号"
            )

        # 只有 admin 可以执行删除操作
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以删除用户"
            )

        user = UserService.get_user_by_id(db, user_id)

        # admin 不能删除其他 admin
        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="管理员之间不能相互删除"
            )

        db.delete(user)
        db.commit()

        logger.info(f"用户已删除: {user.username} (ID: {user.id})")

    @staticmethod
    def reset_password(db: Session, user_id: int, current_user: User) -> str:
        """
        重置用户密码（仅管理员可重置普通用户密码）
        
        密码重置为：用户名_邮箱前缀
        例如：用户名为 john，邮箱为 john@example.com，则密码为 john_john
        
        Args:
            db: 数据库会话
            user_id: 要重置密码的用户ID
            current_user: 当前操作用户（必须是admin）
            
        Returns:
            str: 密码规则字符串
            
        Raises:
            HTTPException: 权限不足或目标用户不是普通用户
        """
        # 只有 admin 可以重置密码
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以重置密码"
            )

        user = UserService.get_user_by_id(db, user_id)

        # 只能重置 user 角色的密码，不能重置 admin 的密码
        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="不能重置管理员的密码"
            )

        try:
            # 生成新密码：用户名_邮箱前缀
            email_prefix = user.email.split("@")[0]
            new_password = f"{user.username}_{email_prefix}"

            # 更新密码
            user.password_hash = get_password_hash(new_password)
            user.updated_at = datetime.now()
            db.commit()

            logger.info(f"管理员重置用户密码: {user.username} (ID: {user.id})")
            return "新的密码为:用户名_邮箱前缀"
        except Exception as e:
            db.rollback()
            logger.error(f"重置密码失败: {str(e)}")
            return "修改失败"


# 全局用户服务实例
user_service = UserService()

