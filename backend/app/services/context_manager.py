"""
上下文管理器
负责管理对话上下文的生命周期
"""
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.utils.redis_client import redis_client
from app.models.chat_history import ChatHistory

logger = logging.getLogger(__name__)


class ContextManager:
    """
    对话上下文管理器
    
    职责：
    1. 管理Redis中的对话上下文
    2. 实现上下文轮次限制（最多10轮）
    3. 处理上下文的加载和持久化
    4. 构建发送给LLM的消息列表
    """
    
    def __init__(self):
        self.redis = redis_client
        self.max_turns = settings.MAX_CONTEXT_TURNS
        self.max_tokens = settings.MAX_CONTEXT_TOKENS
    
    def init_context(
        self,
        session_id: str,
        user_id: int,
        robot_id: int,
        system_prompt: str = ""
    ) -> bool:
        """
        初始化新会话的上下文
        
        Args:
            session_id: 会话UUID
            user_id: 用户ID
            robot_id: 机器人ID
            system_prompt: 系统提示词
            
        Returns:
            是否成功
        """
        return self.redis.init_session_context(
            session_id=session_id,
            user_id=user_id,
            robot_id=robot_id,
            system_prompt=system_prompt
        )
    
    def get_or_load_context(
        self,
        db: Session,
        session_id: str,
        user_id: int,
        robot_id: int,
        system_prompt: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        获取上下文，如果Redis中不存在则从MySQL加载
        
        Args:
            db: 数据库会话
            session_id: 会话UUID
            user_id: 用户ID
            robot_id: 机器人ID
            system_prompt: 系统提示词
            
        Returns:
            上下文数据
        """
        # 1. 尝试从Redis获取
        context = self.redis.get_session_context(session_id)
        
        if context:
            # 更新活跃会话时间戳
            self.redis.update_active_session(user_id, session_id)
            return context
        
        # 2. Redis中不存在，从MySQL加载历史
        logger.info(f"Redis中不存在上下文，从MySQL加载: {session_id}")
        
        # 初始化上下文
        self.redis.init_session_context(
            session_id=session_id,
            user_id=user_id,
            robot_id=robot_id,
            system_prompt=system_prompt
        )
        
        # 从MySQL加载历史消息
        history_messages = db.query(ChatHistory).filter(
            ChatHistory.session_id == session_id
        ).order_by(ChatHistory.sequence.asc()).all()
        
        if history_messages:
            # 转换为消息列表
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "tokens": msg.total_tokens or 0,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else ""
                }
                for msg in history_messages
            ]
            
            # 加载到Redis
            self.redis.load_context_from_history(session_id, messages)
        
        return self.redis.get_session_context(session_id)
    
    def add_user_message(
        self,
        session_id: str,
        content: str,
        tokens: int = 0
    ) -> bool:
        """
        添加用户消息
        
        Args:
            session_id: 会话UUID
            content: 消息内容
            tokens: Token数量
            
        Returns:
            是否成功
        """
        return self.redis.add_message(
            session_id=session_id,
            role="user",
            content=content,
            tokens=tokens
        )
    
    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        tokens: int = 0
    ) -> bool:
        """
        添加助手消息
        
        Args:
            session_id: 会话UUID
            content: 消息内容
            tokens: Token数量
            
        Returns:
            是否成功
        """
        return self.redis.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            tokens=tokens
        )
    
    def build_llm_messages(
        self,
        session_id: str,
        system_prompt: str,
        current_question: str,
        retrieved_contexts: List[str] = None
    ) -> List[Dict[str, str]]:
        """
        构建发送给LLM的完整消息列表
        
        Args:
            session_id: 会话UUID
            system_prompt: 系统提示词
            current_question: 当前用户问题
            retrieved_contexts: 检索到的上下文（可选）
            
        Returns:
            消息列表，格式为 [{"role": "...", "content": "..."}]
        """
        messages = []
        
        # 1. 系统提示词
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 2. 历史对话上下文
        context_messages = self.redis.get_context_messages(session_id)
        for msg in context_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # 3. 当前用户问题（如果有检索上下文，拼接到问题中）
        user_content = current_question
        if retrieved_contexts:
            context_text = "\n\n".join(retrieved_contexts)
            user_content = f"""## 参考资料：
{context_text}

## 用户问题：
{current_question}"""
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def get_turn_count(self, session_id: str) -> int:
        """
        获取当前对话轮次数
        
        Args:
            session_id: 会话UUID
            
        Returns:
            轮次数
        """
        context = self.redis.get_session_context(session_id)
        if context:
            return context.get("turn_count", 0)
        return 0
    
    def check_context_exists(self, session_id: str) -> bool:
        """
        检查上下文是否存在于Redis
        
        Args:
            session_id: 会话UUID
            
        Returns:
            是否存在
        """
        return self.redis.get_session_context(session_id) is not None
    
    def clear_context(self, session_id: str) -> bool:
        """
        清空会话上下文
        
        Args:
            session_id: 会话UUID
            
        Returns:
            是否成功
        """
        return self.redis.delete_session_context(session_id)
    
    def acquire_session_lock(self, session_id: str) -> bool:
        """
        获取会话锁（防止并发请求）
        
        Args:
            session_id: 会话UUID
            
        Returns:
            是否获取成功
        """
        return self.redis.acquire_lock(session_id)
    
    def release_session_lock(self, session_id: str) -> bool:
        """
        释放会话锁
        
        Args:
            session_id: 会话UUID
            
        Returns:
            是否成功
        """
        return self.redis.release_lock(session_id)
    
    def rewrite_query_with_context(
        self,
        session_id: str,
        current_query: str
    ) -> str:
        """
        基于上下文重写查询（用于提升检索效果）
        
        对于多轮对话，用户的查询可能包含指代词（如"它"、"这个"等），
        需要结合上下文进行查询重写以获得更好的检索结果。
        
        Args:
            session_id: 会话UUID
            current_query: 当前查询
            
        Returns:
            重写后的查询（简单实现：拼接最近一轮的问答）
        """
        context_messages = self.redis.get_context_messages(session_id)
        
        if not context_messages or len(context_messages) < 2:
            # 没有历史或历史不足，直接返回原查询
            return current_query
        
        # 获取最近一轮对话
        recent_messages = context_messages[-2:]  # 最后2条消息
        
        # 简单的查询重写：将最近的问答作为上下文
        context_parts = []
        for msg in recent_messages:
            if msg["role"] == "user":
                context_parts.append(f"上一个问题：{msg['content'][:100]}")
            elif msg["role"] == "assistant":
                context_parts.append(f"上一个回答摘要：{msg['content'][:200]}")
        
        if context_parts:
            # 拼接上下文和当前查询
            rewritten_query = f"{' '.join(context_parts)} 当前问题：{current_query}"
            return rewritten_query
        
        return current_query


# 全局上下文管理器实例
context_manager = ContextManager()
