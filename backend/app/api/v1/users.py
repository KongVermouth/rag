"""
用户管理API路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserDetail, UserUpdate, UserListResponse, PasswordChange
from app.services.user_service import user_service
from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter()


@router.get("", response_model=UserListResponse, summary="获取用户列表")
def get_users(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    keyword: str = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取用户列表（仅管理员）
    
    支持按用户名或邮箱搜索
    
    注意：只返回 role 为 user 的用户，不返回其他 admin 用户
    """
    return user_service.get_users(db, current_user, skip, limit, keyword)


@router.get("/{user_id}", response_model=UserDetail, summary="获取用户详情")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取指定用户的详细信息（仅管理员）
    
    注意：只能查看 role 为 user 的用户，不能查看其他 admin 用户
    """
    user = user_service.get_user_detail(db, user_id, current_user)
    return UserDetail.model_validate(user)


@router.put("/{user_id}", response_model=UserDetail, summary="更新用户信息")
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新用户信息（仅管理员）
    
    - 只能修改 role 为 user 的用户信息
    - 不能修改其他 admin 的信息
    """
    updated_user = user_service.update_user(db, user_id, user_data, current_user)
    return UserDetail.model_validate(updated_user)


@router.post("/me/change-password", summary="修改密码")
def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    修改当前用户的密码
    
    修改密码后当前 token 将失效，需要重新登录
    """
    user_service.change_password(db, current_user, password_data)
    return {"message": "密码修改成功，请重新登录"}


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除用户（仅管理员可删除普通用户）
    
    权限规则：
    - 只有 admin 可以删除 user
    - admin 之间不能相互删除
    - 不能删除自己的账号
    """
    user_service.delete_user(db, user_id, current_user)
    return {"message": "用户删除成功"}


@router.post("/{user_id}/reset-password", summary="重置用户密码")
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    重置用户密码（仅管理员可重置普通用户密码）
    
    密码重置规则：用户名_邮箱前缀
    例如：用户名为 john，邮箱为 john@example.com，则新密码为 john_john
    
    权限规则：
    - 只有 admin 可以重置密码
    - 只能重置普通用户的密码，不能重置 admin 的密码
    """
    result = user_service.reset_password(db, user_id, current_user)
    if result == "修改失败":
        return {"message": result}
    return {"message": "密码重置成功", "password_rule": result}
