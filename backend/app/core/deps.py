"""
依赖注入函数
用于FastAPI路由的依赖项
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User


# HTTP Bearer认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_token: Optional[str] = Header(None, alias="X-Token"),
    token: Optional[str] = Query(None, description="认证令牌"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前登录用户
    支持多种方式获取令牌:
    1. Authorization: Bearer <token>
    2. X-Token: <token> (Header)
    3. token: <token> (Query Parameter)
    """
    auth_token = None
    if credentials:
        auth_token = credentials.credentials
    elif x_token:
        auth_token = x_token
    elif token:
        auth_token = token
    
    if auth_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 解码JWT令牌
    payload = decode_access_token(auth_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 获取用户ID
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 获取令牌签发时间
    token_iat = payload.get("iat")
    
    # 查询用户
    result = await db.execute(select(User).filter(User.id == int(user_id)))
    user = result.scalars().first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户状态
    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账号已被禁用"
        )
    
    # 检查密码是否在 token 签发后被修改
    if user.password_changed_at and token_iat:
        # 将 token_iat 转换为 timezone-aware 的 datetime 对象
        token_issued_at = datetime.fromtimestamp(token_iat, tz=timezone.utc)
        # 将 password_changed_at 转换为 timezone-aware（如果是 naive datetime）
        pwd_changed_at = user.password_changed_at
        if pwd_changed_at.tzinfo is None:
            pwd_changed_at = pwd_changed_at.replace(tzinfo=timezone.utc)
        # 如果密码修改时间晚于 token 签发时间，则 token 已失效
        if pwd_changed_at > token_issued_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码已修改，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前活跃用户（状态正常）
    
    Args:
        current_user: 当前用户
    
    Returns:
        当前用户对象
    """
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    要求管理员权限
    
    Args:
        current_user: 当前用户
    
    Returns:
        当前用户对象
    
    Raises:
        HTTPException: 403 权限不足
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return current_user


def verify_resource_owner(
    resource_user_id: int,
    current_user: User
) -> bool:
    """
    验证资源所有权
    
    Args:
        resource_user_id: 资源所属用户ID
        current_user: 当前用户
    
    Returns:
        是否有权限（管理员或资源所有者）
    """
    # 管理员拥有所有权限
    if current_user.role == "admin":
        return True
    
    # 普通用户只能访问自己的资源
    return resource_user_id == current_user.id


def check_resource_permission(
    resource_user_id: int,
    current_user: User
):
    """
    检查资源权限，无权限则抛出异常
    
    Args:
        resource_user_id: 资源所属用户ID
        current_user: 当前用户
    
    Raises:
        HTTPException: 403 权限不足
    """
    if not verify_resource_owner(resource_user_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此资源"
        )
