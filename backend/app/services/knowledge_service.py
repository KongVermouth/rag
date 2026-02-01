"""
知识库管理服务 (异步)
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from fastapi import HTTPException, status

from app.models.user import User
from app.models.knowledge import Knowledge
from app.models.llm import LLM
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, KnowledgeListResponse, KnowledgeDetail
from app.utils.milvus_client import milvus_client
from app.utils.es_client import es_client
from app.utils.embedding import get_embedding_model

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库管理服务类"""

    def __init__(self):
        self.milvus_client = milvus_client
        self.es_client = es_client

    async def create_knowledge(self, db: AsyncSession, knowledge_data: KnowledgeCreate, current_user: User) -> Knowledge:
        """创建知识库"""
        # 验证Embedding模型是否存在
        result = await db.execute(
            select(LLM).where(LLM.id == knowledge_data.embed_llm_id, LLM.model_type == "embedding")
        )
        embed_llm = result.scalar_one_or_none()
        if not embed_llm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Embedding模型不存在或类型不正确"
            )

        # 生成Milvus集合名称
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
        await db.commit()
        await db.refresh(new_knowledge)

        # 创建Milvus向量集合 (Async)
        try:
            # 动态获取Embedding模型的实际维度
            embedding_model = get_embedding_model()
            embedding_dim = embedding_model.get_embedding_dim()
            logger.info(f"Embedding模型维度: {embedding_dim}")
            
            await self.milvus_client.create_collection(
                collection_name=vector_collection_name,
                dim=embedding_dim,
                description=f"Knowledge {new_knowledge.name} vectors"
            )
            logger.info(f"创建Milvus集合: {vector_collection_name}")
        except Exception as e:
            # 如果Milvus集合创建失败，回滚数据库
            await db.delete(new_knowledge)
            await db.commit()
            logger.error(f"创建Milvus集合失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建向量集合失败: {str(e)}"
            )

        logger.info(f"创建知识库: {new_knowledge.name} (ID: {new_knowledge.id})")
        return new_knowledge

    async def get_knowledge_by_id(self, db: AsyncSession, knowledge_id: int, current_user: User) -> Knowledge:
        """获取知识库详情"""
        logger.info(f"DEBUG: Entering get_knowledge_by_id with ID={knowledge_id}, user_id={current_user.id}")
        
        # 使用最显式的查询方式
        from sqlalchemy import select
        stmt = select(Knowledge).where(Knowledge.id == int(knowledge_id))
        result = await db.execute(stmt)
        knowledge = result.scalar_one_or_none()
        
        if not knowledge:
            logger.warning(f"DEBUG: Knowledge still not found for ID={knowledge_id}")
            # 记录数据库中现有的所有 ID，帮助定位是否连错了库
            all_ids_result = await db.execute(select(Knowledge.id))
            all_ids = all_ids_result.scalars().all()
            logger.info(f"DEBUG: Available IDs in DB: {all_ids}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"知识库 [ID={knowledge_id}] 不存在"
            )

        # 权限检查
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            logger.warning(f"DEBUG: Permission denied: KB.user_id={knowledge.user_id}, Current.id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此知识库"
            )

        logger.info(f"DEBUG: Successfully found knowledge: {knowledge.name}")
        return knowledge

    async def get_knowledges(
        self,
        db: AsyncSession,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None
    ) -> KnowledgeListResponse:
        """获取知识库列表"""
        query = select(Knowledge)

        # 非管理员只能查看自己的知识库
        if current_user.role != "admin":
            query = query.where(Knowledge.user_id == current_user.id)

        # 关键词搜索
        if keyword:
            query = query.where(Knowledge.name.ilike(f"%{keyword}%"))

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # 分页
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        knowledges = result.scalars().all()

        return KnowledgeListResponse(
            total=total,
            items=[KnowledgeDetail.model_validate(k) for k in knowledges]
        )

    async def update_knowledge(
        self,
        db: AsyncSession,
        knowledge_id: int,
        knowledge_data: KnowledgeUpdate,
        current_user: User
    ) -> Knowledge:
        """更新知识库"""
        knowledge = await self.get_knowledge_by_id(db, knowledge_id, current_user)

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
        await db.commit()
        await db.refresh(knowledge)

        logger.info(f"更新知识库: {knowledge.name} (ID: {knowledge.id})")
        return knowledge

    async def delete_knowledge(self, db: AsyncSession, knowledge_id: int, current_user: User) -> None:
        """删除知识库"""
        knowledge = await self.get_knowledge_by_id(db, knowledge_id, current_user)

        # 权限检查
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此知识库"
            )

        # 删除Milvus向量集合 (Async)
        try:
            await self.milvus_client.drop_collection(knowledge.vector_collection_name)
            logger.info(f"删除Milvus集合: {knowledge.vector_collection_name}")
        except Exception as e:
            logger.warning(f"删除Milvus集合失败: {e}")

        # 删除ES索引中的相关数据 (Async)
        try:
            await self.es_client.delete_by_knowledge(knowledge_id)
            logger.info(f"删除ES索引中知识库{knowledge_id}的数据")
        except Exception as e:
            logger.warning(f"删除ES索引失败: {e}")

        # 删除数据库记录（包括关联的文档）
        await db.delete(knowledge)
        await db.commit()

        logger.info(f"删除知识库: {knowledge.name} (ID: {knowledge.id})")


# 全局知识库服务实例
knowledge_service = KnowledgeService()
