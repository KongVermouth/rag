"""
知识库管理服务
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.knowledge import Knowledge
from app.models.llm import LLM
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, KnowledgeListResponse, KnowledgeDetail
from app.utils.milvus_client import MilvusClient
from app.utils.es_client import ESClient
from app.utils.embedding import get_embedding_model

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库管理服务类"""

    def __init__(self):
        self.milvus_client = MilvusClient()
        self.es_client = ESClient()

    def create_knowledge(self, db: Session, knowledge_data: KnowledgeCreate, current_user: User) -> Knowledge:
        """
        创建知识库
        
        Args:
            db: 数据库会话
            knowledge_data: 知识库创建数据
            current_user: 当前用户
            
        Returns:
            Knowledge: 新创建的知识库对象
        """
        # 验证Embedding模型是否存在
        embed_llm = db.query(LLM).filter(
            LLM.id == knowledge_data.embed_llm_id,
            LLM.model_type == "embedding"
        ).first()
        if not embed_llm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Embedding模型不存在或类型不正确"
            )

        # 生成Milvus集合名称（只使用数字、字母和下划线，避免中文字符导致Milvus报错）
        vector_collection_name = f"kb_{current_user.id}_{int(datetime.now().timestamp() * 1000)}"

        # 创建知识库记录
        new_knowledge = Knowledge(
            user_id=current_user.id,
            name=knowledge_data.name,
            embed_llm_id=knowledge_data.embed_llm_id,
            vector_collection_name=vector_collection_name,
            chunk_size=knowledge_data.chunk_size,
            chunk_overlap=knowledge_data.chunk_overlap,
            description=knowledge_data.description,
            document_count=0,
            total_chunks=0,
            status=1,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_knowledge)
        db.commit()
        db.refresh(new_knowledge)

        # 创建Milvus向量集合
        try:
            # 动态获取Embedding模型的实际维度
            embedding_model = get_embedding_model()
            embedding_dim = embedding_model.get_embedding_dim()
            logger.info(f"Embedding模型维度: {embedding_dim}")
            
            self.milvus_client.create_collection(
                collection_name=vector_collection_name,
                dim=embedding_dim,
                description=f"Knowledge {new_knowledge.name} vectors"
            )
            logger.info(f"创建Milvus集合: {vector_collection_name}")
        except Exception as e:
            # 如果Milvus集合创建失败，回滚数据库
            db.delete(new_knowledge)
            db.commit()
            logger.error(f"创建Milvus集合失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建向量集合失败: {str(e)}"
            )

        logger.info(f"创建知识库: {new_knowledge.name} (ID: {new_knowledge.id})")
        return new_knowledge

    def get_knowledge_by_id(self, db: Session, knowledge_id: int, current_user: User) -> Knowledge:
        """获取知识库详情"""
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="知识库不存在"
            )

        # 权限检查：只能查看自己的或管理员可查看所有
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此知识库"
            )

        return knowledge

    def get_knowledges(
        self,
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None
    ) -> KnowledgeListResponse:
        """
        获取知识库列表
        
        Args:
            db: 数据库会话
            current_user: 当前用户
            skip: 跳过记录数
            limit: 返回记录数
            keyword: 搜索关键词
            
        Returns:
            KnowledgeListResponse: 知识库列表响应
        """
        query = db.query(Knowledge)

        # 非管理员只能查看自己的知识库
        if current_user.role != "admin":
            query = query.filter(Knowledge.user_id == current_user.id)

        # 关键词搜索
        if keyword:
            query = query.filter(Knowledge.name.like(f"%{keyword}%"))

        total = query.count()
        knowledges = query.offset(skip).limit(limit).all()

        return KnowledgeListResponse(
            total=total,
            items=[KnowledgeDetail.model_validate(k) for k in knowledges]
        )

    def update_knowledge(
        self,
        db: Session,
        knowledge_id: int,
        knowledge_data: KnowledgeUpdate,
        current_user: User
    ) -> Knowledge:
        """
        更新知识库
        
        Args:
            db: 数据库会话
            knowledge_id: 知识库ID
            knowledge_data: 更新数据
            current_user: 当前用户
            
        Returns:
            Knowledge: 更新后的知识库对象
        """
        knowledge = self.get_knowledge_by_id(db, knowledge_id, current_user)

        # 权限检查：只能修改自己的
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此知识库"
            )

        # 更新字段
        if knowledge_data.name is not None:
            knowledge.name = knowledge_data.name
        if knowledge_data.description is not None:
            knowledge.description = knowledge_data.description
        if knowledge_data.status is not None:
            knowledge.status = knowledge_data.status

        knowledge.updated_at = datetime.now()
        db.commit()
        db.refresh(knowledge)

        logger.info(f"更新知识库: {knowledge.name} (ID: {knowledge.id})")
        return knowledge

    def delete_knowledge(self, db: Session, knowledge_id: int, current_user: User) -> None:
        """
        删除知识库
        
        Args:
            db: 数据库会话
            knowledge_id: 知识库ID
            current_user: 当前用户
        """
        knowledge = self.get_knowledge_by_id(db, knowledge_id, current_user)

        # 权限检查
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此知识库"
            )

        # 删除Milvus向量集合
        try:
            self.milvus_client.drop_collection(knowledge.vector_collection_name)
            logger.info(f"删除Milvus集合: {knowledge.vector_collection_name}")
        except Exception as e:
            logger.warning(f"删除Milvus集合失败: {e}")

        # 删除ES索引中的相关数据
        try:
            self.es_client.delete_by_knowledge(knowledge_id)
            logger.info(f"删除ES索引中知识库{knowledge_id}的数据")
        except Exception as e:
            logger.warning(f"删除ES索引失败: {e}")

        # 删除数据库记录（包括关联的文档）
        db.delete(knowledge)
        db.commit()

        logger.info(f"删除知识库: {knowledge.name} (ID: {knowledge.id})")


# 全局知识库服务实例
knowledge_service = KnowledgeService()
