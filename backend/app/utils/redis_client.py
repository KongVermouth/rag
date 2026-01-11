"""
Redis客户端工具类
用于会话上下文管理和缓存
"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import redis
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端封装"""
    
    # Key前缀
    PREFIX = "rag"
    
    # Key模板
    KEY_SESSION_CONTEXT = f"{PREFIX}:session:{{session_id}}:context"
    KEY_SESSION_MESSAGES = f"{PREFIX}:session:{{session_id}}:messages"
    KEY_SESSION_LOCK = f"{PREFIX}:session:{{session_id}}:lock"
    KEY_USER_ACTIVE_SESSIONS = f"{PREFIX}:user:{{user_id}}:active_sessions"
    
    def __init__(self):
        self._client: Optional[Redis] = None
    
    @property
    def client(self) -> Redis:
        """获取Redis客户端（懒加载）"""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
        return self._client
    
    def ping(self) -> bool:
        """测试连接"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            return False
    
    # ==================== 会话上下文操作 ====================
    
    def init_session_context(
        self,
        session_id: str,
        user_id: int,
        robot_id: int,
        system_prompt: str = ""
    ) -> bool:
        """
        初始化会话上下文
        
        Args:
            session_id: 会话UUID
            user_id: 用户ID
            robot_id: 机器人ID
            system_prompt: 系统提示词
            
        Returns:
            是否成功
        """
        key = self.KEY_SESSION_CONTEXT.format(session_id=session_id)
        try:
            pipe = self.client.pipeline()
            pipe.hset(key, mapping={
                "user_id": str(user_id),
                "robot_id": str(robot_id),
                "turn_count": "0",
                "system_prompt": system_prompt,
                "total_tokens": "0",
                "last_active": datetime.now().isoformat()
            })
            pipe.expire(key, settings.SESSION_CONTEXT_TTL)
            pipe.execute()
            
            # 添加到用户活跃会话列表
            self._add_to_active_sessions(user_id, session_id)
            
            logger.info(f"初始化会话上下文: {session_id}")
            return True
        except Exception as e:
            logger.error(f"初始化会话上下文失败: {e}")
            return False
    
    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话上下文元数据
        
        Args:
            session_id: 会话UUID
            
        Returns:
            上下文数据字典，不存在返回None
        """
        key = self.KEY_SESSION_CONTEXT.format(session_id=session_id)
        try:
            data = self.client.hgetall(key)
            if not data:
                return None
            
            # 刷新过期时间
            self.client.expire(key, settings.SESSION_CONTEXT_TTL)
            
            return {
                "user_id": int(data.get("user_id", 0)),
                "robot_id": int(data.get("robot_id", 0)),
                "turn_count": int(data.get("turn_count", 0)),
                "system_prompt": data.get("system_prompt", ""),
                "total_tokens": int(data.get("total_tokens", 0)),
                "last_active": data.get("last_active", "")
            }
        except Exception as e:
            logger.error(f"获取会话上下文失败: {e}")
            return None
    
    def update_session_context(
        self,
        session_id: str,
        turn_count: Optional[int] = None,
        total_tokens: Optional[int] = None
    ) -> bool:
        """
        更新会话上下文
        
        Args:
            session_id: 会话UUID
            turn_count: 轮次数
            total_tokens: 总Token数
            
        Returns:
            是否成功
        """
        key = self.KEY_SESSION_CONTEXT.format(session_id=session_id)
        try:
            updates = {"last_active": datetime.now().isoformat()}
            if turn_count is not None:
                updates["turn_count"] = str(turn_count)
            if total_tokens is not None:
                updates["total_tokens"] = str(total_tokens)
            
            self.client.hset(key, mapping=updates)
            self.client.expire(key, settings.SESSION_CONTEXT_TTL)
            return True
        except Exception as e:
            logger.error(f"更新会话上下文失败: {e}")
            return False
    
    def delete_session_context(self, session_id: str) -> bool:
        """删除会话上下文"""
        try:
            context_key = self.KEY_SESSION_CONTEXT.format(session_id=session_id)
            messages_key = self.KEY_SESSION_MESSAGES.format(session_id=session_id)
            self.client.delete(context_key, messages_key)
            return True
        except Exception as e:
            logger.error(f"删除会话上下文失败: {e}")
            return False
    
    # ==================== 对话消息操作 ====================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0
    ) -> bool:
        """
        添加消息到会话上下文
        
        Args:
            session_id: 会话UUID
            role: 角色 (user/assistant)
            content: 消息内容
            tokens: Token数量
            
        Returns:
            是否成功
        """
        key = self.KEY_SESSION_MESSAGES.format(session_id=session_id)
        context_key = self.KEY_SESSION_CONTEXT.format(session_id=session_id)
        
        message = {
            "role": role,
            "content": content,
            "tokens": tokens,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            pipe = self.client.pipeline()
            
            # 添加消息到列表头部
            pipe.lpush(key, json.dumps(message, ensure_ascii=False))
            
            # 获取当前消息数量
            message_count = self.client.llen(key)
            
            # 计算轮次（每2条消息=1轮：user+assistant）
            current_turns = (message_count + 1) // 2
            
            # 如果超过限制，移除最旧的消息
            max_messages = settings.MAX_CONTEXT_TURNS * 2
            if message_count >= max_messages:
                # 移除超出的消息
                pipe.rpop(key)
            
            # 更新过期时间
            pipe.expire(key, settings.SESSION_CONTEXT_TTL)
            
            # 更新上下文元数据中的轮次数
            pipe.hset(context_key, "turn_count", str(min(current_turns, settings.MAX_CONTEXT_TURNS)))
            pipe.hset(context_key, "last_active", datetime.now().isoformat())
            pipe.expire(context_key, settings.SESSION_CONTEXT_TTL)
            
            pipe.execute()
            
            logger.debug(f"添加消息到会话 {session_id}, role={role}")
            return True
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            return False
    
    def get_context_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取会话的上下文消息列表（用于构建LLM Prompt）
        
        Args:
            session_id: 会话UUID
            
        Returns:
            消息列表（按时间正序，旧->新）
        """
        key = self.KEY_SESSION_MESSAGES.format(session_id=session_id)
        try:
            # 获取所有消息（Redis List按LPUSH顺序存储，最新的在前）
            messages = self.client.lrange(key, 0, -1)
            
            if not messages:
                return []
            
            # 刷新过期时间
            self.client.expire(key, settings.SESSION_CONTEXT_TTL)
            
            # 解析并反转为正序（旧->新）
            parsed_messages = [json.loads(m) for m in messages]
            parsed_messages.reverse()
            
            return parsed_messages
        except Exception as e:
            logger.error(f"获取上下文消息失败: {e}")
            return []
    
    def clear_messages(self, session_id: str) -> bool:
        """清空会话消息"""
        key = self.KEY_SESSION_MESSAGES.format(session_id=session_id)
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"清空消息失败: {e}")
            return False
    
    # ==================== 用户活跃会话操作 ====================
    
    def _add_to_active_sessions(self, user_id: int, session_id: str) -> None:
        """添加到用户活跃会话列表"""
        key = self.KEY_USER_ACTIVE_SESSIONS.format(user_id=user_id)
        try:
            # 使用当前时间戳作为分数
            score = datetime.now().timestamp()
            self.client.zadd(key, {session_id: score})
            self.client.expire(key, settings.SESSION_ACTIVE_TTL)
        except Exception as e:
            logger.error(f"添加活跃会话失败: {e}")
    
    def update_active_session(self, user_id: int, session_id: str) -> None:
        """更新活跃会话的时间戳"""
        self._add_to_active_sessions(user_id, session_id)
    
    def get_user_active_sessions(
        self,
        user_id: int,
        limit: int = 20
    ) -> List[str]:
        """
        获取用户的活跃会话列表（按最近活跃时间排序）
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            
        Returns:
            会话ID列表
        """
        key = self.KEY_USER_ACTIVE_SESSIONS.format(user_id=user_id)
        try:
            # 按分数降序获取（最近活跃的在前）
            sessions = self.client.zrevrange(key, 0, limit - 1)
            return sessions
        except Exception as e:
            logger.error(f"获取活跃会话列表失败: {e}")
            return []
    
    def remove_from_active_sessions(self, user_id: int, session_id: str) -> None:
        """从活跃会话列表中移除"""
        key = self.KEY_USER_ACTIVE_SESSIONS.format(user_id=user_id)
        try:
            self.client.zrem(key, session_id)
        except Exception as e:
            logger.error(f"移除活跃会话失败: {e}")
    
    # ==================== 会话锁操作 ====================
    
    def acquire_lock(self, session_id: str, timeout: int = 30) -> bool:
        """
        获取会话锁（防止并发）
        
        Args:
            session_id: 会话UUID
            timeout: 锁超时时间（秒）
            
        Returns:
            是否获取成功
        """
        key = self.KEY_SESSION_LOCK.format(session_id=session_id)
        try:
            # 使用SETNX实现锁
            result = self.client.set(key, "1", nx=True, ex=timeout)
            return result is True
        except Exception as e:
            logger.error(f"获取会话锁失败: {e}")
            return False
    
    def release_lock(self, session_id: str) -> bool:
        """释放会话锁"""
        key = self.KEY_SESSION_LOCK.format(session_id=session_id)
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"释放会话锁失败: {e}")
            return False
    
    # ==================== 批量操作 ====================
    
    def load_context_from_history(
        self,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        从MySQL历史记录加载上下文到Redis
        
        Args:
            session_id: 会话UUID
            messages: 历史消息列表（按时间正序）
            
        Returns:
            是否成功
        """
        key = self.KEY_SESSION_MESSAGES.format(session_id=session_id)
        try:
            # 只加载最近的N轮对话
            max_messages = settings.MAX_CONTEXT_TURNS * 2
            recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
            
            pipe = self.client.pipeline()
            
            # 清空现有消息
            pipe.delete(key)
            
            # 按倒序添加（因为使用LPUSH）
            for msg in reversed(recent_messages):
                message_data = {
                    "role": msg["role"],
                    "content": msg["content"],
                    "tokens": msg.get("tokens", 0),
                    "timestamp": msg.get("timestamp", datetime.now().isoformat())
                }
                pipe.lpush(key, json.dumps(message_data, ensure_ascii=False))
            
            pipe.expire(key, settings.SESSION_CONTEXT_TTL)
            pipe.execute()
            
            return True
        except Exception as e:
            logger.error(f"加载历史上下文失败: {e}")
            return False


# 全局Redis客户端实例
redis_client = RedisClient()
