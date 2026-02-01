"""
知识库管理API路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeDetail, 
    KnowledgeListResponse, KnowledgeBrief
)
from app.services.knowledge_service import knowledge_service
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=KnowledgeDetail, summary="创建知识库")
async def create_knowledge(
    knowledge_data: KnowledgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建知识库
    
    - **name**: 知识库名称
    - **embed_llm_id**: Embedding模型ID
    - **chunk_size**: 文本切片大小（默认500）
    - **chunk_overlap**: 文本切片重叠（默认50）
    """
    knowledge = await knowledge_service.create_knowledge(db, knowledge_data, current_user)
    return KnowledgeDetail.model_validate(knowledge)


@router.get("", response_model=KnowledgeListResponse, summary="获取知识库列表")
async def get_knowledges(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    keyword: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取知识库列表
    
    普通用户只能看到自己创建的知识库，管理员可以看到所有知识库
    """
    return await knowledge_service.get_knowledges(db, current_user, skip, limit, keyword)


@router.get("/brief", response_model=list[KnowledgeBrief], summary="获取知识库简要列表")
async def get_knowledges_brief(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取知识库简要列表，用于下拉选择
    """
    knowledges = await knowledge_service.get_knowledges(db, current_user, skip=0, limit=100)
    return [KnowledgeBrief.model_validate(k) for k in knowledges.items]


@router.get("/test-connectivity", summary="测试连接性")
async def test_connectivity():
    return {"status": "ok", "message": "Backend is reachable and updated"}


@router.get("/{knowledge_id}", response_model=KnowledgeDetail, summary="获取知识库详情")
async def get_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定知识库的详细信息
    """
    knowledge = await knowledge_service.get_knowledge_by_id(db, knowledge_id, current_user)
    return KnowledgeDetail.model_validate(knowledge)


@router.put("/{knowledge_id}", response_model=KnowledgeDetail, summary="更新知识库")
async def update_knowledge(
    knowledge_id: int,
    knowledge_data: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新知识库信息
    
    只能修改自己创建的知识库
    """
    updated_knowledge = await knowledge_service.update_knowledge(
        db, knowledge_id, knowledge_data, current_user
    )
    return KnowledgeDetail.model_validate(updated_knowledge)


@router.delete("/{knowledge_id}", summary="删除知识库")
async def delete_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除知识库
    
    会同时删除关联的向量集合和文档
    """
    await knowledge_service.delete_knowledge(db, knowledge_id, current_user)
    return {"message": "知识库删除成功"}
