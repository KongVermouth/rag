"""
机器人管理API路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.robot import (
    RobotCreate, RobotUpdate, RobotDetail, 
    RobotListResponse, RobotBrief
)
from app.services.robot_service import robot_service
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=RobotDetail, summary="创建机器人")
def create_robot(
    robot_data: RobotCreate,
    db: Session = Depends(get_db),
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
    robot = robot_service.create_robot(db, robot_data, current_user)
    
    # 添加知识库ID列表
    robot_detail = RobotDetail.model_validate(robot)
    robot_detail.knowledge_ids = robot_data.knowledge_ids
    return robot_detail


@router.get("", response_model=RobotListResponse, summary="获取机器人列表")
def get_robots(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    keyword: str = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取机器人列表
    
    普通用户只能看到自己创建的机器人，管理员可以看到所有机器人
    """
    return robot_service.get_robots(db, current_user, skip, limit, keyword)


@router.get("/brief", response_model=list[RobotBrief], summary="获取机器人简要列表")
def get_robots_brief(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取机器人简要列表，用于下拉选择
    """
    robots = robot_service.get_robots(db, current_user, skip=0, limit=100)
    return [RobotBrief.model_validate(r) for r in robots.items]


@router.get("/{robot_id}", response_model=RobotDetail, summary="获取机器人详情")
def get_robot(
    robot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定机器人的详细信息
    """
    robot = robot_service.get_robot_by_id(db, robot_id, current_user)
    robot_detail = RobotDetail.model_validate(robot)
    robot_detail.knowledge_ids = robot_service.get_robot_knowledge_ids(db, robot_id)
    return robot_detail


@router.put("/{robot_id}", response_model=RobotDetail, summary="更新机器人")
def update_robot(
    robot_id: int,
    robot_data: RobotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新机器人配置
    
    只能修改自己创建的机器人
    """
    updated_robot = robot_service.update_robot(db, robot_id, robot_data, current_user)
    robot_detail = RobotDetail.model_validate(updated_robot)
    robot_detail.knowledge_ids = robot_service.get_robot_knowledge_ids(db, robot_id)
    return robot_detail


@router.delete("/{robot_id}", summary="删除机器人")
def delete_robot(
    robot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除机器人
    
    只能删除自己创建的机器人
    """
    robot_service.delete_robot(db, robot_id, current_user)
    return {"message": "机器人删除成功"}
