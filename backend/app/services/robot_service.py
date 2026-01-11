"""
机器人管理服务
"""
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.robot import Robot
from app.models.robot_knowledge import RobotKnowledge
from app.models.llm import LLM
from app.models.knowledge import Knowledge
from app.schemas.robot import RobotCreate, RobotUpdate, RobotListResponse, RobotDetail

logger = logging.getLogger(__name__)


class RobotService:
    """机器人管理服务类"""

    @staticmethod
    def create_robot(db: Session, robot_data: RobotCreate, current_user: User) -> Robot:
        """
        创建机器人
        
        Args:
            db: 数据库会话
            robot_data: 机器人创建数据
            current_user: 当前用户
            
        Returns:
            Robot: 新创建的机器人对象
        """
        # 验证Chat LLM模型是否存在
        chat_llm = db.query(LLM).filter(
            LLM.id == robot_data.chat_llm_id,
            LLM.model_type == "chat"
        ).first()
        if not chat_llm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat LLM模型不存在或类型不正确"
            )

        # 验证知识库是否存在且有权限
        for kb_id in robot_data.knowledge_ids:
            knowledge = db.query(Knowledge).filter(Knowledge.id == kb_id).first()
            if not knowledge:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"知识库{kb_id}不存在"
                )
            if knowledge.user_id != current_user.id and current_user.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无权访问知识库{kb_id}"
                )

        # 创建机器人记录
        new_robot = Robot(
            user_id=current_user.id,
            name=robot_data.name,
            chat_llm_id=robot_data.chat_llm_id,
            system_prompt=robot_data.system_prompt,
            top_k=robot_data.top_k,
            temperature=robot_data.temperature,
            max_tokens=robot_data.max_tokens,
            description=robot_data.description,
            status=1,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_robot)
        db.flush()  # 获取robot_id

        # 创建机器人-知识库关联
        for kb_id in robot_data.knowledge_ids:
            robot_kb = RobotKnowledge(
                robot_id=new_robot.id,
                knowledge_id=kb_id
            )
            db.add(robot_kb)

        db.commit()
        db.refresh(new_robot)

        logger.info(f"创建机器人: {new_robot.name} (ID: {new_robot.id})")
        return new_robot

    @staticmethod
    def get_robot_by_id(db: Session, robot_id: int, current_user: User) -> Robot:
        """获取机器人详情"""
        robot = db.query(Robot).filter(Robot.id == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="机器人不存在"
            )

        # 权限检查：只能查看自己的或管理员可查看所有
        if robot.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此机器人"
            )

        return robot

    @staticmethod
    def get_robot_knowledge_ids(db: Session, robot_id: int) -> List[int]:
        """获取机器人关联的知识库ID列表"""
        robot_kbs = db.query(RobotKnowledge).filter(RobotKnowledge.robot_id == robot_id).all()
        return [rk.knowledge_id for rk in robot_kbs]

    @staticmethod
    def get_robots(
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None
    ) -> RobotListResponse:
        """
        获取机器人列表
        
        Args:
            db: 数据库会话
            current_user: 当前用户
            skip: 跳过记录数
            limit: 返回记录数
            keyword: 搜索关键词
            
        Returns:
            RobotListResponse: 机器人列表响应
        """
        query = db.query(Robot)

        # 非管理员只能查看自己的机器人
        if current_user.role != "admin":
            query = query.filter(Robot.user_id == current_user.id)

        # 关键词搜索
        if keyword:
            query = query.filter(Robot.name.like(f"%{keyword}%"))

        total = query.count()
        robots = query.offset(skip).limit(limit).all()

        # 添加知识库ID列表
        items = []
        for robot in robots:
            robot_detail = RobotDetail.model_validate(robot)
            robot_detail.knowledge_ids = RobotService.get_robot_knowledge_ids(db, robot.id)
            items.append(robot_detail)

        return RobotListResponse(
            total=total,
            items=items
        )

    @staticmethod
    def update_robot(
        db: Session,
        robot_id: int,
        robot_data: RobotUpdate,
        current_user: User
    ) -> Robot:
        """
        更新机器人
        
        Args:
            db: 数据库会话
            robot_id: 机器人ID
            robot_data: 更新数据
            current_user: 当前用户
            
        Returns:
            Robot: 更新后的机器人对象
        """
        robot = RobotService.get_robot_by_id(db, robot_id, current_user)

        # 权限检查：只能修改自己的
        if robot.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此机器人"
            )

        # 更新字段
        if robot_data.name is not None:
            robot.name = robot_data.name
        if robot_data.chat_llm_id is not None:
            robot.chat_llm_id = robot_data.chat_llm_id
        if robot_data.system_prompt is not None:
            robot.system_prompt = robot_data.system_prompt
        if robot_data.top_k is not None:
            robot.top_k = robot_data.top_k
        if robot_data.temperature is not None:
            robot.temperature = robot_data.temperature
        if robot_data.max_tokens is not None:
            robot.max_tokens = robot_data.max_tokens
        if robot_data.description is not None:
            robot.description = robot_data.description
        if robot_data.status is not None:
            robot.status = robot_data.status

        # 更新知识库关联
        if robot_data.knowledge_ids is not None:
            # 删除旧的关联
            db.query(RobotKnowledge).filter(RobotKnowledge.robot_id == robot_id).delete()
            # 添加新的关联
            for kb_id in robot_data.knowledge_ids:
                robot_kb = RobotKnowledge(
                    robot_id=robot_id,
                    knowledge_id=kb_id
                )
                db.add(robot_kb)

        robot.updated_at = datetime.now()
        db.commit()
        db.refresh(robot)

        logger.info(f"更新机器人: {robot.name} (ID: {robot.id})")
        return robot

    @staticmethod
    def delete_robot(db: Session, robot_id: int, current_user: User) -> None:
        """
        删除机器人
        
        Args:
            db: 数据库会话
            robot_id: 机器人ID
            current_user: 当前用户
        """
        robot = RobotService.get_robot_by_id(db, robot_id, current_user)

        # 权限检查
        if robot.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此机器人"
            )

        # 删除关联的知识库记录
        db.query(RobotKnowledge).filter(RobotKnowledge.robot_id == robot_id).delete()

        # 删除机器人记录
        db.delete(robot)
        db.commit()

        logger.info(f"删除机器人: {robot.name} (ID: {robot.id})")


# 全局机器人服务实例
robot_service = RobotService()
