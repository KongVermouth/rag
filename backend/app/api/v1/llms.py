"""
LLM模型管理API路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.llm import LLMCreate, LLMUpdate, LLMDetail, LLMListResponse, LLMBrief
from app.services.llm_service import llm_service
from app.core.deps import require_admin, get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=LLMDetail, summary="创建LLM模型")
def create_llm(
    llm_data: LLMCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建LLM模型配置（仅管理员）
    
    - **name**: 模型名称
    - **model_type**: 模型类型（embedding/chat）
    - **provider**: 提供商（local/openai/azure等）
    - **model_name**: 模型标识
    """
    llm = llm_service.create_llm(db, llm_data, current_user)
    return LLMDetail.model_validate(llm)


@router.get("", response_model=LLMListResponse, summary="获取LLM模型列表")
def get_llms(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    model_type: str = Query(None, description="模型类型过滤（embedding/chat）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取LLM模型列表（仅管理员）
    """
    return llm_service.get_llms(db, current_user, skip, limit, model_type)


@router.get("/options", response_model=list[LLMBrief], summary="获取可用LLM选项")
def get_llm_options(
    model_type: str = Query(None, description="模型类型过滤（embedding/chat）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取可用的LLM模型选项（所有登录用户）
    
    返回状态为启用的LLM模型列表，供用户选择使用。
    """
    llms = llm_service.get_available_llm_options(db, model_type)
    return [LLMBrief.model_validate(llm) for llm in llms]


@router.get("/brief", response_model=list[LLMBrief], summary="获取LLM简要列表（下拉选择）")
def get_llms_brief(
    model_type: str = Query(None, description="模型类型过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取LLM简要列表（仅管理员），用于下拉选择
    """
    llms = llm_service.get_llms(db, current_user, skip=0, limit=100, model_type=model_type)
    return [LLMBrief.model_validate(llm) for llm in llms.items]


@router.get("/{llm_id}", response_model=LLMDetail, summary="获取LLM模型详情")
def get_llm(
    llm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取指定LLM模型的详细信息（仅管理员）
    """
    llm = llm_service.get_llm_by_id(db, llm_id, current_user)
    return LLMDetail.model_validate(llm)


@router.put("/{llm_id}", response_model=LLMDetail, summary="更新LLM模型")
def update_llm(
    llm_id: int,
    llm_data: LLMUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新LLM模型配置（仅管理员）
    """
    updated_llm = llm_service.update_llm(db, llm_id, llm_data, current_user)
    return LLMDetail.model_validate(updated_llm)


@router.delete("/{llm_id}", summary="删除LLM模型")
def delete_llm(
    llm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除LLM模型（仅管理员）
    """
    llm_service.delete_llm(db, llm_id, current_user)
    return {"message": "LLM模型删除成功"}
