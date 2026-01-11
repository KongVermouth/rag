"""
会话服务
负责会话的CRUD操作和历史记录管理
"""
import uuid
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
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
    
    def create_session(
        self,
        db: Session,
        user: User,
        robot_id: int,
        title: Optional[str] = None
    ) -> SessionModel:
        """
        创建新会话
        
        Args:
            db: 数据库会话
            user: 当前用户
            robot_id: 机器人ID
            title: 会话标题（可选）
            
        Returns:
            创建的会话对象
        """
        # 验证机器人存在且用户有权限
        robot = db.query(Robot).filter(
            Robot.id == robot_id,
            Robot.user_id == user.id
        ).first()
        
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
        db.commit()
        db.refresh(session)
        
        # 初始化Redis上下文
        context_manager.init_context(
            session_id=session_id,
            user_id=user.id,
            robot_id=robot_id,
            system_prompt=robot.system_prompt or ""
        )
        
        logger.info(f"创建新会话: {session_id}, user={user.id}, robot={robot_id}")
        
        return session
    
    def get_or_create_session(
        self,
        db: Session,
        user: User,
        robot_id: int,
        session_id: Optional[str] = None
    ) -> Tuple[SessionModel, bool]:
        """
        获取或创建会话
        
        Args:
            db: 数据库会话
            user: 当前用户
            robot_id: 机器人ID
            session_id: 会话ID（可选，不传则创建新会话）
            
        Returns:
            (会话对象, 是否新创建)
        """
        if session_id:
            # 获取现有会话
            session = self.get_session_by_id(db, session_id, user)
            if session:
                # 验证robot_id匹配
                if session.robot_id != robot_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="会话与机器人不匹配"
                    )
                return session, False
        
        # 创建新会话
        session = self.create_session(db, user, robot_id)
        return session, True
    
    def get_session_by_id(
        self,
        db: Session,
        session_id: str,
        user: User
    ) -> Optional[SessionModel]:
        """
        根据ID获取会话
        
        Args:
            db: 数据库会话
            session_id: 会话UUID
            user: 当前用户
            
        Returns:
            会话对象，不存在返回None
        """
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == user.id,
            SessionModel.status != "deleted"
        ).first()
        
        return session
    
    def get_user_sessions(
        self,
        db: Session,
        user: User,
        robot_id: Optional[int] = None,
        status_filter: str = "active",
        skip: int = 0,
        limit: int = 20
    ) -> SessionListResponse:
        """
        获取用户的会话列表
        
        Args:
            db: 数据库会话
            user: 当前用户
            robot_id: 机器人ID筛选（可选）
            status_filter: 状态筛选
            skip: 跳过数量
            limit: 返回数量
            
        Returns:
            会话列表响应
        """
        query = db.query(SessionModel).filter(
            SessionModel.user_id == user.id,
            SessionModel.status == status_filter
        )
        
        if robot_id:
            query = query.filter(SessionModel.robot_id == robot_id)
        
        # 获取总数
        total = query.count()
        
        # 分页查询（置顶的在前，然后按最后消息时间排序）
        sessions = query.order_by(
            desc(SessionModel.is_pinned),
            desc(SessionModel.last_message_at)
        ).offset(skip).limit(limit).all()
        
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
    
    def update_session(
        self,
        db: Session,
        session_id: str,
        user: User,
        update_data: SessionUpdate
    ) -> SessionModel:
        """
        更新会话信息
        
        Args:
            db: 数据库会话
            session_id: 会话UUID
            user: 当前用户
            update_data: 更新数据
            
        Returns:
            更新后的会话对象
        """
        session = self.get_session_by_id(db, session_id, user)
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
                # 如果归档，清除Redis上下文
                if update_data.status == "archived":
                    context_manager.clear_context(session_id)
                    redis_client.remove_from_active_sessions(user.id, session_id)
        
        db.commit()
        db.refresh(session)
        
        return session
    
    def delete_session(
        self,
        db: Session,
        session_id: str,
        user: User
    ) -> bool:
        """
        删除会话（软删除）
        
        Args:
            db: 数据库会话
            session_id: 会话UUID
            user: 当前用户
            
        Returns:
            是否成功
        """
        session = self.get_session_by_id(db, session_id, user)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
        # 软删除
        session.status = "deleted"
        db.commit()
        
        # 清除Redis上下文
        context_manager.clear_context(session_id)
        redis_client.remove_from_active_sessions(user.id, session_id)
        
        logger.info(f"删除会话: {session_id}")
        
        return True
    
    def get_session_detail(
        self,
        db: Session,
        session_id: str,
        user: User,
        message_limit: int = 50
    ) -> SessionDetailResponse:
        """
        获取会话详情（包含历史消息）
        
        Args:
            db: 数据库会话
            session_id: 会话UUID
            user: 当前用户
            message_limit: 消息数量限制
            
        Returns:
            会话详情响应
        """
        session = self.get_session_by_id(db, session_id, user)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        
        # 获取历史消息
        messages = db.query(ChatHistory).filter(
            ChatHistory.session_id == session_id
        ).order_by(ChatHistory.sequence.asc()).limit(message_limit).all()
        
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
    
    def save_chat_message(
        self,
        db: Session,
        session_id: str,
        role: str,
        content: str,
        contexts: List[dict] = None,
        token_usage: dict = None,
        time_metrics: dict = None
    ) -> ChatHistory:
        """
        保存聊天消息到历史记录
        
        Args:
            db: 数据库会话
            session_id: 会话UUID
            role: 角色 (user/assistant)
            content: 消息内容
            contexts: 检索上下文（仅assistant）
            token_usage: Token统计（仅assistant）
            time_metrics: 时间指标（仅assistant）
            
        Returns:
            保存的消息记录
        """
        # 获取当前会话的消息序号
        max_seq = db.query(ChatHistory).filter(
            ChatHistory.session_id == session_id
        ).count()
        
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
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
        
        if session:
            session.message_count = max_seq + 1
            session.last_message_at = datetime.now()
            
            # 如果是第一条用户消息，更新标题
            if role == "user" and max_seq == 0:
                # 使用问题的前50个字符作为标题
                session.title = content[:50] + ("..." if len(content) > 50 else "")
        
        db.commit()
        db.refresh(chat_history)
        
        return chat_history
    
    def update_feedback(
        self,
        db: Session,
        user: User,
        feedback_request: FeedbackRequest
    ) -> bool:
        """
        更新消息反馈
        
        Args:
            db: 数据库会话
            user: 当前用户
            feedback_request: 反馈请求
            
        Returns:
            是否成功
        """
        # 获取消息
        message = db.query(ChatHistory).filter(
            ChatHistory.message_id == feedback_request.message_id
        ).first()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="消息不存在"
            )
        
        # 验证用户权限
        session = db.query(SessionModel).filter(
            SessionModel.session_id == message.session_id,
            SessionModel.user_id == user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此消息"
            )
        
        # 更新反馈
        message.feedback = feedback_request.feedback
        message.feedback_comment = feedback_request.comment
        
        db.commit()
        
        return True
    
    def archive_inactive_sessions(self, db: Session) -> int:
        """
        归档不活跃的会话（定时任务调用）
        
        Args:
            db: 数据库会话
            
        Returns:
            归档的会话数量
        """
        threshold = datetime.now() - timedelta(days=settings.SESSION_ARCHIVE_DAYS)
        
        # 查找需要归档的会话
        sessions_to_archive = db.query(SessionModel).filter(
            SessionModel.status == "active",
            SessionModel.last_message_at < threshold
        ).all()
        
        count = 0
        for session in sessions_to_archive:
            session.status = "archived"
            # 清除Redis上下文
            context_manager.clear_context(session.session_id)
            count += 1
        
        db.commit()
        
        if count > 0:
            logger.info(f"归档了 {count} 个不活跃会话")
        
        return count


# 全局会话服务实例
session_service = SessionService()
