"""
用户相关的Pydantic模式
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ==================== 用户注册 ====================
class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名，3-50个字符")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=128, description="密码，至少6个字符")
    role: str = Field(default="user", pattern="^(user|admin)$", description="用户角色：user（普通用户）或 admin（管理员），默认为 user")


# ==================== 用户登录 ====================
class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """登录成功后的Token响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


# ==================== 用户信息 ====================
class UserBase(BaseModel):
    """用户基础信息"""
    username: str = Field(..., description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    role: str = Field(..., description="角色：user/admin")
    status: int = Field(..., description="状态：0-禁用，1-启用")


class UserDetail(UserBase):
    """用户详细信息（响应）"""
    id: int = Field(..., description="用户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """用户信息更新请求"""
    email: Optional[EmailStr] = Field(None, description="邮箱")
    role: Optional[str] = Field(None, pattern="^(user|admin)$", description="角色：user/admin")
    status: Optional[int] = Field(None, ge=0, le=1, description="状态：0-禁用，1-启用")


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码，至少6个字符")


# ==================== 用户列表 ====================
class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int = Field(..., description="总数")
    items: list[UserDetail] = Field(..., description="用户列表")
