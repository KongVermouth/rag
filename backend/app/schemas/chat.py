"""
对话/问答相关的Pydantic模式
"""
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ==================== 会话状态枚举 ====================
class SessionStatus(str, Enum):
    """会话状态枚举"""
    ACTIVE = "active"      # 活跃
    ARCHIVED = "archived"  # 已归档
    DELETED = "deleted"    # 已删除


# 允许的会话状态值
ALLOWED_SESSION_STATUS = {"active", "archived", "deleted"}


# ==================== 对话请求 ====================
class ChatRequest(BaseModel):
    """对话请求"""
    robot_id: int = Field(..., description="机器人ID")
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: Optional[str] = Field(None, description="会话ID（用于多轮对话，不传则创建新会话）")
    stream: bool = Field(default=False, description="是否流式返回")


# ==================== 检索到的上下文 ====================
class RetrievedContext(BaseModel):
    """检索到的上下文片段"""
    chunk_id: str = Field(..., description="切片ID")
    document_id: int = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    content: str = Field(..., description="切片内容")
    score: float = Field(..., ge=0.0, le=1.0, description="相似度分数（0-1）")
    source: str = Field(..., description="检索来源：vector/keyword/hybrid")


# ==================== 对话响应 ====================
class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str = Field(..., description="会话ID")
    question: str = Field(..., description="用户问题")
    answer: str = Field(..., description="机器人回答")
    contexts: List[RetrievedContext] = Field(default_factory=list, description="检索到的上下文")
    token_usage: dict = Field(default_factory=dict, description="Token使用统计")
    response_time: float = Field(..., description="响应时间（秒）")


# ==================== 流式响应（SSE） ====================
class ChatStreamChunk(BaseModel):
    """流式响应的数据块"""
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="增量内容")
    is_finished: bool = Field(default=False, description="是否完成")
    reasoning_content: Optional[str] = Field(None, description="思考过程内容（部分模型如DeepSeek R1/OpenAI o1支持）")
    contexts: Optional[List[RetrievedContext]] = Field(None, description="检索上下文（仅在首个chunk返回）")
    token_usage: Optional[dict] = Field(None, description="Token使用统计（仅在最后chunk返回）")


# ==================== 会话历史 ====================
class ConversationMessage(BaseModel):
    """会话消息"""
    role: str = Field(..., description="角色：user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳")


class ConversationHistory(BaseModel):
    """会话历史"""
    session_id: str = Field(..., description="会话ID")
    robot_id: int = Field(..., description="机器人ID")
    messages: List[ConversationMessage] = Field(default_factory=list, description="消息列表")
    created_at: str = Field(..., description="会话创建时间")


# ==================== 会话管理 ====================
class SessionCreate(BaseModel):
    """创建会话请求"""
    robot_id: int = Field(..., description="机器人ID")
    title: Optional[str] = Field(None, max_length=200, description="会话标题")


class SessionUpdate(BaseModel):
    """更新会话请求"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题")
    is_pinned: Optional[bool] = Field(None, description="是否置顶")
    status: Optional[Literal["active", "archived", "deleted"]] = Field(
        None, 
        description="状态: active=活跃, archived=已归档, deleted=已删除"
    )
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """校验status字段值"""
        if v is not None and v not in ALLOWED_SESSION_STATUS:
            raise ValueError(f'状态值无效，必须是: {list(ALLOWED_SESSION_STATUS)}')
        return v


class SessionInfo(BaseModel):
    """会话信息响应"""
    session_id: str = Field(..., description="会话UUID")
    robot_id: int = Field(..., description="机器人ID")
    title: Optional[str] = Field(None, description="会话标题")
    summary: Optional[str] = Field(None, description="会话摘要")
    message_count: int = Field(default=0, description="消息数量")
    status: str = Field(default="active", description="会话状态")
    is_pinned: bool = Field(default=False, description="是否置顶")
    last_message_at: Optional[datetime] = Field(None, description="最后消息时间")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int = Field(..., description="总数")
    sessions: List[SessionInfo] = Field(default_factory=list, description="会话列表")


class ChatHistoryItem(BaseModel):
    """历史消息项"""
    message_id: str = Field(..., description="消息ID")
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")
    contexts: Optional[List[RetrievedContext]] = Field(None, description="检索上下文")
    token_usage: Optional[dict] = Field(None, description="Token统计")
    feedback: Optional[int] = Field(None, description="用户反馈")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class SessionDetailResponse(BaseModel):
    """会话详情响应（包含历史消息）"""
    session: SessionInfo = Field(..., description="会话信息")
    messages: List[ChatHistoryItem] = Field(default_factory=list, description="历史消息")


class FeedbackRequest(BaseModel):
    """反馈请求"""
    message_id: str = Field(..., description="消息ID")
    feedback: int = Field(..., ge=-1, le=1, description="反馈: 1=有用, -1=无用")
    comment: Optional[str] = Field(None, max_length=500, description="反馈评论")


# ==================== 知识库测试请求 ====================
class KnowledgeTestRequest(BaseModel):
    """知识库测试请求（不调用LLM，仅返回检索结果）"""
    knowledge_id: int = Field(..., description="知识库ID")
    query: str = Field(..., min_length=1, max_length=500, description="测试查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回Top-K结果")
    retrieval_mode: str = Field(default="hybrid", description="检索模式：vector/keyword/hybrid")


class KnowledgeTestResponse(BaseModel):
    """知识库测试响应"""
    query: str = Field(..., description="查询内容")
    retrieval_mode: str = Field(..., description="检索模式")
    results: List[RetrievedContext] = Field(default_factory=list, description="检索结果")
    retrieval_time: float = Field(..., description="检索耗时（秒）")
