"""
机器人管理API路由
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
import time
from collections import defaultdict

from app.db.session import get_db
from app.schemas.robot import (
    RobotCreate, RobotUpdate, RobotDetail, 
    RobotListResponse, RobotBrief,
    RetrievalTestRequest, RetrievalTestResponse, RetrievalTestResultItem
)
from app.services.robot_service import robot_service
from app.services.rag_service import rag_service
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()

# 简单的内存限流器: {user_id: [timestamps]}
rate_limiter = defaultdict(list)

def check_rate_limit(user_id: int):
    now = time.time()
    # 清理 1 分钟之前的记录
    rate_limiter[user_id] = [t for t in rate_limiter[user_id] if now - t < 60]
    if len(rate_limiter[user_id]) >= 30:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试 (限流 30 req/min)"
        )
    rate_limiter[user_id].append(now)

@router.post("/{robot_id}/retrieval-test", response_model=RetrievalTestResponse, summary="机器人召回测试")
async def retrieval_test(
    robot_id: int,
    test_data: RetrievalTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    机器人召回测试：
    - 输入查询词、Top-K、阈值
    - 返回检索到的文档片段及得分
    - 仅做内存计算，不持久化
    - 限流 30 req/min
    """
    # 1. 限流检查
    check_rate_limit(current_user.id)

    # 2. 获取机器人及其关联知识库
    robot = await robot_service.get_robot_by_id(db, robot_id, current_user)
    knowledge_ids = await robot_service.get_robot_knowledge_ids(db, robot_id)
    
    if not knowledge_ids:
        return RetrievalTestResponse(results=[])

    # 3. 调用检索服务 (混合检索)
    # 注意：threshold 过滤在 RAG 服务外处理，或者扩展 hybrid_retrieve
    contexts = await rag_service.hybrid_retrieve(
        db=db,
        robot=robot,
        knowledge_ids=knowledge_ids,
        query=test_data.query,
        top_k=test_data.top_k
    )

    # 4. 阈值过滤
    results = []
    for ctx in contexts:
        if ctx.score >= test_data.threshold:
            results.append(RetrievalTestResultItem(
                id=ctx.chunk_id,
                score=ctx.score,
                content=ctx.content,
                document_id=ctx.document_id,
                filename=ctx.filename
            ))

    return RetrievalTestResponse(results=results)


@router.post("", response_model=RobotDetail, summary="创建机器人")
async def create_robot(
    robot_data: RobotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建对话机器人
    
    - **name**: 机器人名称
    - **chat_llm_id**: 对话LLM模型ID
    - **knowledge_ids**: 关联的知识库ID列表
    - **system_prompt**: 系统提示词
    - **top_k**: 检索Top-K数量
    - **temperature**: 生成温度
    - **max_tokens**: 最大生成Token数
    """
    robot = await robot_service.create_robot(db, robot_data, current_user)
    
    # 添加知识库ID列表
    robot_detail = RobotDetail.model_validate(robot)
    robot_detail.knowledge_ids = robot_data.knowledge_ids
    return robot_detail


@router.get("", response_model=RobotListResponse, summary="获取机器人列表")
async def get_robots(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    keyword: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取机器人列表
    
    普通用户只能看到自己创建的机器人，管理员可以看到所有机器人
    """
    return await robot_service.get_robots(db, current_user, skip, limit, keyword)


@router.get("/brief", response_model=list[RobotBrief], summary="获取机器人简要列表")
async def get_robots_brief(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取机器人简要列表，用于下拉选择
    """
    robots = await robot_service.get_robots(db, current_user, skip=0, limit=100)
    return [RobotBrief.model_validate(r) for r in robots.items]


@router.get("/{robot_id}", response_model=RobotDetail, summary="获取机器人详情")
async def get_robot(
    robot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定机器人的详细信息
    """
    robot = await robot_service.get_robot_by_id(db, robot_id, current_user)
    robot_detail = RobotDetail.model_validate(robot)
    robot_detail.knowledge_ids = await robot_service.get_robot_knowledge_ids(db, robot_id)
    return robot_detail


@router.put("/{robot_id}", response_model=RobotDetail, summary="更新机器人")
async def update_robot(
    robot_id: int,
    robot_data: RobotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新机器人配置
    
    只能修改自己创建的机器人
    """
    updated_robot = await robot_service.update_robot(db, robot_id, robot_data, current_user)
    robot_detail = RobotDetail.model_validate(updated_robot)
    robot_detail.knowledge_ids = await robot_service.get_robot_knowledge_ids(db, robot_id)
    return robot_detail


@router.delete("/{robot_id}", summary="删除机器人")
async def delete_robot(
    robot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除机器人
    
    只能删除自己创建的机器人
    """
    await robot_service.delete_robot(db, robot_id, current_user)
    return {"message": "机器人删除成功"}
