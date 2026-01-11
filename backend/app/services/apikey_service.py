"""
API Key管理服务
"""
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.apikey import APIKey
from app.models.llm import LLM
from app.schemas.apikey import (
    APIKeyCreate, 
    APIKeyUpdate, 
    APIKeyListResponse, 
    APIKeyDetail,
    APIKeyOption,
    APIKeyOptionsResponse,
    APIKeyValidation
)
from app.core.security import api_key_crypto, mask_api_key

logger = logging.getLogger(__name__)


class APIKeyService:
    """API Key管理服务类"""

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
                detail="只有管理员才能管理API Key"
            )

    @staticmethod
    def _verify_llm_exists(db: Session, llm_id: int) -> LLM:
        """
        验证LLM模型是否存在
        
        Args:
            db: 数据库会话
            llm_id: LLM模型ID
            
        Returns:
            LLM: LLM模型对象
            
        Raises:
            HTTPException: 404 LLM不存在
        """
        llm = db.query(LLM).filter(LLM.id == llm_id).first()
        if not llm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="关联的LLM模型不存在"
            )
        return llm

    @staticmethod
    def _apikey_to_detail(apikey: APIKey) -> APIKeyDetail:
        """
        将APIKey模型转换为APIKeyDetail响应
        
        Args:
            apikey: APIKey模型对象
            
        Returns:
            APIKeyDetail: 详情响应对象
        """
        # 解密并脱敏显示API Key
        try:
            decrypted_key = api_key_crypto.decrypt(apikey.api_key_encrypted)
            masked_key = mask_api_key(decrypted_key)
        except Exception:
            masked_key = "****解密失败****"
        
        return APIKeyDetail(
            id=apikey.id,
            llm_id=apikey.llm_id,
            user_id=apikey.user_id,
            alias=apikey.alias,
            api_key_masked=masked_key,
            description=apikey.description,
            status=apikey.status,
            created_at=apikey.created_at,
            updated_at=apikey.updated_at
        )

    # ==================== 管理员CRUD操作 ====================
    
    @staticmethod
    def create_apikey(db: Session, apikey_data: APIKeyCreate, current_user: User) -> APIKeyDetail:
        """
        创建API Key（仅管理员）
        
        Args:
            db: 数据库会话
            apikey_data: API Key创建数据
            current_user: 当前用户（必须是管理员）
            
        Returns:
            APIKeyDetail: 新创建的API Key详情
            
        Raises:
            HTTPException: 403 权限不足 / 404 LLM不存在
        """
        # 权限校验
        APIKeyService._check_admin_permission(current_user)
        
        # 验证LLM存在
        APIKeyService._verify_llm_exists(db, apikey_data.llm_id)
        
        # 加密API Key
        encrypted_key = api_key_crypto.encrypt(apikey_data.api_key)
        
        # 创建新记录
        new_apikey = APIKey(
            user_id=current_user.id,
            llm_id=apikey_data.llm_id,
            alias=apikey_data.alias,
            api_key_encrypted=encrypted_key,
            description=apikey_data.description,
            status=1,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_apikey)
        db.commit()
        db.refresh(new_apikey)
        
        logger.info(f"创建API Key: {new_apikey.alias} (ID: {new_apikey.id})")
        return APIKeyService._apikey_to_detail(new_apikey)

    @staticmethod
    def get_apikey_by_id(db: Session, apikey_id: int, current_user: User) -> APIKeyDetail:
        """
        获取API Key详情（仅管理员）
        
        Args:
            db: 数据库会话
            apikey_id: API Key ID
            current_user: 当前用户（必须是管理员）
            
        Returns:
            APIKeyDetail: API Key详情
            
        Raises:
            HTTPException: 403 权限不足 / 404 不存在
        """
        # 权限校验
        APIKeyService._check_admin_permission(current_user)
        
        apikey = db.query(APIKey).filter(APIKey.id == apikey_id).first()
        if not apikey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key不存在"
            )
        
        return APIKeyService._apikey_to_detail(apikey)

    @staticmethod
    def get_apikeys(
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        llm_id: Optional[int] = None
    ) -> APIKeyListResponse:
        """
        获取API Key列表（仅管理员）
        
        Args:
            db: 数据库会话
            current_user: 当前用户（必须是管理员）
            skip: 跳过记录数
            limit: 返回记录数
            llm_id: 按LLM ID过滤（可选）
            
        Returns:
            APIKeyListResponse: API Key列表响应
            
        Raises:
            HTTPException: 403 权限不足
        """
        # 权限校验
        APIKeyService._check_admin_permission(current_user)
        
        query = db.query(APIKey)
        
        # 按LLM ID过滤
        if llm_id is not None:
            query = query.filter(APIKey.llm_id == llm_id)
        
        total = query.count()
        apikeys = query.order_by(APIKey.created_at.desc()).offset(skip).limit(limit).all()
        
        items = [APIKeyService._apikey_to_detail(apikey) for apikey in apikeys]
        
        return APIKeyListResponse(total=total, items=items)

    @staticmethod
    def update_apikey(
        db: Session, 
        apikey_id: int, 
        apikey_data: APIKeyUpdate, 
        current_user: User
    ) -> APIKeyDetail:
        """
        更新API Key（仅管理员）
        
        Args:
            db: 数据库会话
            apikey_id: API Key ID
            apikey_data: 更新数据
            current_user: 当前用户（必须是管理员）
            
        Returns:
            APIKeyDetail: 更新后的API Key详情
            
        Raises:
            HTTPException: 403 权限不足 / 404 不存在
        """
        # 权限校验
        APIKeyService._check_admin_permission(current_user)
        
        apikey = db.query(APIKey).filter(APIKey.id == apikey_id).first()
        if not apikey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key不存在"
            )
        
        # 更新字段
        if apikey_data.alias is not None:
            apikey.alias = apikey_data.alias
        if apikey_data.api_key is not None:
            # 加密新的API Key
            apikey.api_key_encrypted = api_key_crypto.encrypt(apikey_data.api_key)
        if apikey_data.description is not None:
            apikey.description = apikey_data.description
        if apikey_data.status is not None:
            apikey.status = apikey_data.status
        
        apikey.updated_at = datetime.now()
        db.commit()
        db.refresh(apikey)
        
        logger.info(f"更新API Key: {apikey.alias} (ID: {apikey.id})")
        return APIKeyService._apikey_to_detail(apikey)

    @staticmethod
    def delete_apikey(db: Session, apikey_id: int, current_user: User) -> None:
        """
        删除API Key（仅管理员）
        
        Args:
            db: 数据库会话
            apikey_id: API Key ID
            current_user: 当前用户（必须是管理员）
            
        Raises:
            HTTPException: 403 权限不足 / 404 不存在
        """
        # 权限校验
        APIKeyService._check_admin_permission(current_user)
        
        apikey = db.query(APIKey).filter(APIKey.id == apikey_id).first()
        if not apikey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key不存在"
            )
        
        db.delete(apikey)
        db.commit()
        
        logger.info(f"删除API Key: {apikey.alias} (ID: {apikey.id})")

    # ==================== 普通用户只读操作 ====================
    
    @staticmethod
    def get_available_apikey_options(
        db: Session,
        current_user: User,
        llm_id: Optional[int] = None
    ) -> APIKeyOptionsResponse:
        """
        获取可用的API Key选项（供普通用户选择使用）
        
        只返回状态为启用的API Key，且关联的LLM也必须是启用状态
        
        Args:
            db: 数据库会话
            current_user: 当前用户
            llm_id: 按LLM ID过滤（可选）
            
        Returns:
            APIKeyOptionsResponse: 可用的API Key选项列表
        """
        # 使用 JOIN 查询，确保只返回关联到启用状态 LLM 的 API Key
        query = db.query(APIKey).join(
            LLM, APIKey.llm_id == LLM.id
        ).filter(
            APIKey.status == 1,  # API Key 启用
            LLM.status == 1       # 关联的 LLM 也必须启用
        )
        
        # 按LLM ID过滤
        if llm_id is not None:
            query = query.filter(APIKey.llm_id == llm_id)
        
        apikeys = query.all()
        
        logger.debug(f"查询到 {len(apikeys)} 个可用的 API Key")
        
        # 获取关联的LLM名称
        llm_ids = list(set(apikey.llm_id for apikey in apikeys))
        llms = db.query(LLM).filter(LLM.id.in_(llm_ids), LLM.status == 1).all() if llm_ids else []
        llm_name_map = {llm.id: llm.name for llm in llms}
        
        items = [
            APIKeyOption(
                id=apikey.id,
                llm_id=apikey.llm_id,
                llm_name=llm_name_map.get(apikey.llm_id),
                alias=apikey.alias
            )
            for apikey in apikeys
        ]
        
        return APIKeyOptionsResponse(total=len(items), items=items)

    @staticmethod
    def get_decrypted_apikey(db: Session, apikey_id: int, current_user: User) -> APIKeyValidation:
        """
        获取解密后的API Key（内部使用，用于调用外部API）
        
        Args:
            db: 数据库会话
            apikey_id: API Key ID
            current_user: 当前用户
            
        Returns:
            APIKeyValidation: 包含解密后API Key的验证响应
        """
        apikey = db.query(APIKey).filter(
            APIKey.id == apikey_id,
            APIKey.status == 1
        ).first()
        
        if not apikey:
            return APIKeyValidation(is_valid=False)
        
        try:
            decrypted_key = api_key_crypto.decrypt(apikey.api_key_encrypted)
            return APIKeyValidation(
                is_valid=True,
                llm_id=apikey.llm_id,
                decrypted_key=decrypted_key
            )
        except Exception as e:
            logger.error(f"解密API Key失败: {e}")
            return APIKeyValidation(is_valid=False)


# 全局API Key服务实例
apikey_service = APIKeyService()
