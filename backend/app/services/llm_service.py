"""
LLM模型管理服务
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.llm import LLM
from app.schemas.llm import LLMCreate, LLMUpdate, LLMListResponse, LLMDetail

logger = logging.getLogger(__name__)


class LLMService:
    """LLM模型管理服务类"""

    @staticmethod
    def _check_admin_permission(current_user: User) -> None:
        """
        检查用户是否为管理员
        
        Args:
            current_user: 当前用户
            
        Raises:
            HTTPException: 403 权限不足
        """
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员才能管理大模型"
            )

    @staticmethod
    def create_llm(db: Session, llm_data: LLMCreate, current_user: User) -> LLM:
        """
        创建LLM模型（仅管理员）
        
        Args:
            db: 数据库会话
            llm_data: LLM创建数据
            current_user: 当前用户（必须是管理员）
            
        Returns:
            LLM: 新创建的LLM对象
            
        Raises:
            HTTPException: 403 权限不足
        """
        # 权限校验：只有管理员可以创建
        LLMService._check_admin_permission(current_user)
        new_llm = LLM(
            user_id=current_user.id,
            name=llm_data.name,
            model_type=llm_data.model_type,
            provider=llm_data.provider,
            model_name=llm_data.model_name,
            base_url=llm_data.base_url,
            api_version=llm_data.api_version,
            description=llm_data.description,
            status=1,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_llm)
        db.commit()
        db.refresh(new_llm)

        logger.info(f"创建LLM模型: {new_llm.name} (ID: {new_llm.id})")
        return new_llm

    @staticmethod
    def get_llm_by_id(db: Session, llm_id: int, current_user: User) -> LLM:
        """
        获取LLM模型详情（仅管理员）
        
        Args:
            db: 数据库会话
            llm_id: LLM模型ID
            current_user: 当前用户（必须是管理员）
            
        Returns:
            LLM: LLM模型对象
            
        Raises:
            HTTPException: 403 权限不足或 404 模型不存在
        """
        # 权限校验：只有管理员可以查看
        LLMService._check_admin_permission(current_user)
        
        llm = db.query(LLM).filter(LLM.id == llm_id).first()
        if not llm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LLM模型不存在"
            )

        return llm

    @staticmethod
    def get_llms(
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        model_type: Optional[str] = None
    ) -> LLMListResponse:
        """
        获取LLM模型列表（仅管理员）
        
        Args:
            db: 数据库会话
            current_user: 当前用户（必须是管理员）
            skip: 跳过记录数
            limit: 返回记录数
            model_type: 模型类型过滤（embedding/chat）
            
        Returns:
            LLMListResponse: LLM列表响应
            
        Raises:
            HTTPException: 403 权限不足
        """
        # 权限校验：只有管理员可以查看列表
        LLMService._check_admin_permission(current_user)
        
        query = db.query(LLM)

        # 模型类型过滤
        if model_type:
            query = query.filter(LLM.model_type == model_type)

        total = query.count()
        llms = query.offset(skip).limit(limit).all()

        return LLMListResponse(
            total=total,
            items=[LLMDetail.model_validate(llm) for llm in llms]
        )

    @staticmethod
    def update_llm(db: Session, llm_id: int, llm_data: LLMUpdate, current_user: User) -> LLM:
        """
        更新LLM模型（仅管理员）
        
        Args:
            db: 数据库会话
            llm_id: LLM ID
            llm_data: 更新数据
            current_user: 当前用户（必须是管理员）
            
        Returns:
            LLM: 更新后的LLM对象
            
        Raises:
            HTTPException: 403 权限不足
        """
        # 权限校验：只有管理员可以更新（get_llm_by_id 内部会校验）
        llm = LLMService.get_llm_by_id(db, llm_id, current_user)

        # 更新字段
        if llm_data.name is not None:
            llm.name = llm_data.name
        if llm_data.base_url is not None:
            llm.base_url = llm_data.base_url
        if llm_data.api_version is not None:
            llm.api_version = llm_data.api_version
        if llm_data.description is not None:
            llm.description = llm_data.description
        if llm_data.status is not None:
            llm.status = llm_data.status

        llm.updated_at = datetime.now()
        db.commit()
        db.refresh(llm)

        logger.info(f"更新LLM模型: {llm.name} (ID: {llm.id})")
        return llm

    @staticmethod
    def delete_llm(db: Session, llm_id: int, current_user: User) -> None:
        """
        删除LLM模型（仅管理员）
        
        Args:
            db: 数据库会话
            llm_id: LLM ID
            current_user: 当前用户（必须是管理员）
            
        Raises:
            HTTPException: 403 权限不足
        """
        # 权限校验：只有管理员可以删除（get_llm_by_id 内部会校验）
        llm = LLMService.get_llm_by_id(db, llm_id, current_user)

        # 检查是否有关联的知识库或机器人正在使用
        # TODO: 添加关联检查

        db.delete(llm)
        db.commit()

        logger.info(f"删除LLM模型: {llm.name} (ID: {llm.id})")

    # ==================== 普通用户只读操作 ====================
    
    @staticmethod
    def get_available_llm_options(
        db: Session,
        model_type: Optional[str] = None
    ) -> list[LLMDetail]:
        """
        获取可用的LLM模型选项（供所有登录用户使用）
        
        只返回状态为启用的LLM模型
        
        Args:
            db: 数据库会话
            model_type: 模型类型过滤（embedding/chat）
            
        Returns:
            list[LLMDetail]: 可用的LLM模型列表
        """
        query = db.query(LLM).filter(LLM.status == 1)
        
        if model_type:
            query = query.filter(LLM.model_type == model_type)
        
        llms = query.all()
        return [LLMDetail.model_validate(llm) for llm in llms]


# 全局LLM服务实例
llm_service = LLMService()
