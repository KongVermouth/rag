"""
API密钥管理API路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.services.apikey_service import apikey_service
from app.schemas.apikey import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyDetail,
    APIKeyListResponse,
    APIKeyOptionsResponse
)

router = APIRouter()


# ==================== 管理员CRUD接口 ====================

@router.post("", response_model=APIKeyDetail, summary="创建API Key")
def create_apikey(
    apikey_data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建新的API Key（仅管理员）
    
    - **llm_id**: 关联的LLM模型ID
    - **alias**: 密钥名称/别名
    - **api_key**: API密钥（明文，将被加密存储）
    - **description**: 密钥描述（可选）
    """
    return apikey_service.create_apikey(db, apikey_data, current_user)


@router.get("", response_model=APIKeyListResponse, summary="获取API Key列表")
def get_apikeys(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    llm_id: Optional[int] = Query(None, description="按LLM ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取API Key列表（仅管理员）
    
    支持分页和按LLM ID过滤
    """
    return apikey_service.get_apikeys(db, current_user, skip, limit, llm_id)


@router.get("/options", response_model=APIKeyOptionsResponse, summary="获取可用的API Key选项")
def get_apikey_options(
    llm_id: Optional[int] = Query(None, description="按LLM ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取可用的API Key选项（所有登录用户）
    
    返回状态为启用的API Key列表，供用户选择使用。
    只返回基本信息（ID、别名、关联LLM），不返回敏感信息。
    """
    return apikey_service.get_available_apikey_options(db, current_user, llm_id)


@router.get("/{apikey_id}", response_model=APIKeyDetail, summary="获取API Key详情")
def get_apikey(
    apikey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取指定API Key的详细信息（仅管理员）
    
    API Key会以脱敏形式显示（如：sk-abcd****efgh）
    """
    return apikey_service.get_apikey_by_id(db, apikey_id, current_user)


@router.put("/{apikey_id}", response_model=APIKeyDetail, summary="更新API Key")
def update_apikey(
    apikey_id: int,
    apikey_data: APIKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新API Key（仅管理员）
    
    可更新的字段：
    - **alias**: 密钥名称/别名
    - **api_key**: 新的API密钥
    - **description**: 密钥描述
    - **status**: 状态（0-禁用，1-启用）
    """
    return apikey_service.update_apikey(db, apikey_id, apikey_data, current_user)


@router.delete("/{apikey_id}", summary="删除API Key")
def delete_apikey(
    apikey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除API Key（仅管理员）
    
    删除后不可恢复
    """
    apikey_service.delete_apikey(db, apikey_id, current_user)
    return {"message": "API Key删除成功"}
