"""
会话服务 (异步)
负责会话的CRUD操作和历史记录管理
"""
import uuid
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func, update
from fastapi import HTTPException, status

from app.models.session import Session as SessionModel
from app.models.chat_history import ChatHistory
from app.models.user import User
from app.models.robot import Robot
from app.schemas.chat import (
    SessionCreate, SessionUpdate, SessionInfo, 
    SessionListResponse, ChatHistoryItem, SessionDetailResponse,
    FeedbackRequest, RetrievedContext
)
from app.services.context_manager import context_manager
from app.utils.redis_client import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionService:
    """会话服务类"""
    
    async def create_session(
        self,
        db: AsyncSession,
        user: User,
        robot_id: int,
        title: Optional[str] = None
    ) -> SessionModel:
        """创建新会话"""
        # 验证机器人存在且用户有权限
        result = await db.execute(select(Robot).where(
            Robot.id == robot_id,
            Robot.user_id == user.id
        ))
        robot = result.scalar_one_or_none()
        
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="机器人不存在或无权限"
            )
        
        # 生成会话UUID
        session_id = str(uuid.uuid4())
        
        # 创建会话记录
        session = SessionModel(
            session_id=session_id,
            user_id=user.id,
            robot_id=robot_id,
            title=title or f"新对话 - {datetime.now().strftime('%m/%d %H:%M')}",
            status="active",
            message_count=0
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        # 初始化Redis上下文 (Async)
        await context_manager.init_context(
            session_id=session_id,
            user_id=user.id,
            robot_id=robot_id,
            system_prompt=robot.system_prompt or ""
        )
        
        logger.info(f"创建新会话: {session_id}, user={user.id}, robot={robot_id}")
        
        return session
    
    async def get_or_create_session(
        self,
        db: AsyncSession,
        user: User,
        robot_id: int,
        session_id: Optional[str] = None
    ) -> Tuple[SessionModel, bool]:
        """获取或创建会话"""
        if session_id:
            # 获取现有会话
            session = await self.get_session_by_id(db, session_id, user)
            if session:
                # 验证robot_id匹配
                if session.robot_id != robot_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="会话与机器人不匹配"
                    )
                return session, False
        
        # 创建新会话
        session = await self.create_session(db, user, robot_id)
        return session, True
    
    async def get_session_by_id(
        self,
        db: AsyncSession,
        session_id: str,
        user: User
    ) -> Optional[SessionModel]:
        """根据ID获取会话"""
        result = await db.execute(select(SessionModel).where(
            SessionModel.session_id == session_id,
            SessionModel.user_id == user.id,
            SessionModel.status != "deleted"
        ))
        session = result.scalar_one_or_none()
        
        return session
    
    async def get_user_sessions(
        self,
        db: AsyncSession,
        user: User,
        robot_id: Optional[int] = None,
        status_filter: str = "active",
        skip: int = 0,
        limit: int = 20
    ) -> SessionListResponse:
        """获取用户的会话列表"""
        query = select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.status == status_filter
        )
        
        if robot_id:
            query = query.where(SessionModel.robot_id == robot_id)
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 分页查询（置顶的在前，然后按最后消息时间排序）
        query = query.order_by(
            desc(SessionModel.is_pinned),
            desc(SessionModel.last_message_at)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        # 转换为响应格式
        session_infos = [
            SessionInfo(
                session_id=s.session_id,
                robot_id=s.robot_id,
                title=s.title,
                summary=s.summary,
                message_count=s.message_count,
                status=s.status,
                is_pinned=bool(s.is_pinned),
                last_message_at=s.last_message_at,
                created_at=s.created_at
            )
            for s in sessions
        ]
        
        return SessionListResponse(total=total, sessions=session_infos)
    
    async def update_session(
        self,
        db: AsyncSession,
        session_id: str,
        user: User,
        update_data: SessionUpdate
    ) -> SessionModel:
        """更新会话信息"""
        session = await self.get_session_by_id(db, session_id, user)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
        # 更新字段
        if update_data.title is not None:
            session.title = update_data.title
        if update_data.is_pinned is not None:
            session.is_pinned = 1 if update_data.is_pinned else 0
        if update_data.status is not None:
            if update_data.status in ["active", "archived"]:
                session.status = update_data.status
                # 如果归档，清除Redis上下文 (Async)
                if update_data.status == "archived":
                    await context_manager.clear_context(session_id)
                    await redis_client.remove_from_active_sessions(user.id, session_id)
        
        await db.commit()
        await db.refresh(session)
        
        return session
    
    async def delete_session(
        self,
        db: AsyncSession,
        session_id: str,
        user: User
    ) -> bool:
        """删除会话（软删除）"""
        session = await self.get_session_by_id(db, session_id, user)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
        # 软删除
        session.status = "deleted"
        await db.commit()
        
        # 清除Redis上下文 (Async)
        await context_manager.clear_context(session_id)
        await redis_client.remove_from_active_sessions(user.id, session_id)
        
        logger.info(f"删除会话: {session_id}")
        
        return True
    
    async def get_session_detail(
        self,
        db: AsyncSession,
        session_id: str,
        user: User,
        message_limit: int = 50
    ) -> SessionDetailResponse:
        """获取会话详情（包含历史消息）"""
        session = await self.get_session_by_id(db, session_id, user)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
        # 获取历史消息
        result = await db.execute(
            select(ChatHistory).where(
                ChatHistory.session_id == session_id
            ).order_by(ChatHistory.sequence.asc()).limit(message_limit)
        )
        messages = result.scalars().all()
        
        # 转换响应
        session_info = SessionInfo(
            session_id=session.session_id,
            robot_id=session.robot_id,
            title=session.title,
            summary=session.summary,
            message_count=session.message_count,
            status=session.status,
            is_pinned=bool(session.is_pinned),
            last_message_at=session.last_message_at,
            created_at=session.created_at
        )
        
        message_items = []
        for msg in messages:
            # 解析检索上下文
            contexts = None
            if msg.retrieved_contexts:
                try:
                    contexts = [
                        RetrievedContext(**ctx) 
                        for ctx in msg.retrieved_contexts
                    ]
                except:
                    contexts = None
            
            message_items.append(ChatHistoryItem(
                message_id=msg.message_id,
                role=msg.role,
                content=msg.content,
                contexts=contexts,
                token_usage={
                    "prompt_tokens": msg.prompt_tokens,
                    "completion_tokens": msg.completion_tokens,
                    "total_tokens": msg.total_tokens
                } if msg.role == "assistant" else None,
                feedback=msg.feedback,
                created_at=msg.created_at
            ))
        
        return SessionDetailResponse(session=session_info, messages=message_items)
    
    async def save_chat_message(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        contexts: List[dict] = None,
        token_usage: dict = None,
        time_metrics: dict = None
    ) -> ChatHistory:
        """保存聊天消息到历史记录"""
        # 获取当前会话的消息序号
        count_result = await db.execute(
            select(func.count()).where(ChatHistory.session_id == session_id)
        )
        max_seq = count_result.scalar()
        
        message_id = str(uuid.uuid4())
        
        chat_history = ChatHistory(
            session_id=session_id,
            message_id=message_id,
            role=role,
            content=content,
            sequence=max_seq + 1
        )
        
        # assistant消息的额外信息
        if role == "assistant":
            if contexts:
                chat_history.retrieved_contexts = contexts
                chat_history.referenced_doc_ids = [ctx.get("document_id") for ctx in contexts if ctx.get("document_id")]
            if token_usage:
                chat_history.prompt_tokens = token_usage.get("prompt_tokens", 0)
                chat_history.completion_tokens = token_usage.get("completion_tokens", 0)
                chat_history.total_tokens = token_usage.get("total_tokens", 0)
            if time_metrics:
                chat_history.retrieval_time_ms = time_metrics.get("retrieval_time_ms", 0)
                chat_history.generation_time_ms = time_metrics.get("generation_time_ms", 0)
                chat_history.total_time_ms = time_metrics.get("total_time_ms", 0)
        
        db.add(chat_history)
        
        # 更新会话元数据
        result = await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
        session = result.scalar_one_or_none()
        
        if session:
            session.message_count = max_seq + 1
            session.last_message_at = datetime.now()
            
            # 如果是第一条用户消息，更新标题
            if role == "user" and max_seq == 0:
                # 使用问题的前50个字符作为标题
                session.title = content[:50] + ("..." if len(content) > 50 else "")
        
        await db.commit()
        await db.refresh(chat_history)
        
        return chat_history
    
    async def update_feedback(
        self,
        db: AsyncSession,
        user: User,
        feedback_request: FeedbackRequest
    ) -> bool:
        """更新消息反馈"""
        # 获取消息
        result = await db.execute(select(ChatHistory).where(
            ChatHistory.message_id == feedback_request.message_id
        ))
        message = result.scalar_one_or_none()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="消息不存在"
            )
        
        # 验证用户权限
        session_result = await db.execute(select(SessionModel).where(
            SessionModel.session_id == message.session_id,
            SessionModel.user_id == user.id
        ))
        session = session_result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此消息"
            )
        
        # 更新反馈
        message.feedback = feedback_request.feedback
        message.feedback_comment = feedback_request.comment
        
        await db.commit()
        
        return True
    
    async def archive_inactive_sessions(self, db: AsyncSession) -> int:
        """归档不活跃的会话（定时任务调用）"""
        threshold = datetime.now() - timedelta(days=settings.SESSION_ARCHIVE_DAYS)
        
        # 查找需要归档的会话
        result = await db.execute(select(SessionModel).where(
            SessionModel.status == "active",
            SessionModel.last_message_at < threshold
        ))
        sessions_to_archive = result.scalars().all()
        
        count = 0
        for session in sessions_to_archive:
            session.status = "archived"
            # 清除Redis上下文 (Async)
            await context_manager.clear_context(session.session_id)
            count += 1
        
        if count > 0:
            await db.commit()
            logger.info(f"归档了 {count} 个不活跃会话")
        
        return count


# 全局会话服务实例
session_service = SessionService()
