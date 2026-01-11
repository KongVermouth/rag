"""
认证相关API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserRegister, UserLogin, TokenResponse, UserDetail
from app.services.auth_service import auth_service
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=UserDetail, summary="用户注册")
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    用户注册接口
    
    - **username**: 用户名，3-50个字符
    - **email**: 邮箱地址
    - **password**: 密码，至少6个字符
    - **role**: 用户角色，可选值为 "user"（普通用户）或 "admin"（管理员），默认为 "user"
    """
    user = auth_service.register(db, user_data)
    return UserDetail.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    用户登录接口
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    
    返回访问令牌（JWT）
    """
    return auth_service.login(db, login_data)


@router.get("/me", response_model=UserDetail, summary="获取当前用户信息")
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前登录用户的信息
    
    需要在请求头中携带Bearer Token
    """
    return UserDetail.model_validate(current_user)


@router.post("/refresh", response_model=TokenResponse, summary="刷新Token")
def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌
    
    使用当前Token换取新的Token
    """
    from datetime import timedelta
    from app.core.security import create_access_token
    from app.core.config import settings
    
    expires_delta = timedelta(hours=settings.JWT_EXPIRE_HOURS)
    access_token = create_access_token(
        data={"sub": str(current_user.id), "username": current_user.username, "role": current_user.role},
        expires_delta=expires_delta
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_HOURS * 3600
    )
