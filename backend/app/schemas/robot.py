"""
机器人相关的Pydantic模式
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ==================== 机器人创建 ====================
class RobotCreate(BaseModel):
    """创建机器人请求"""
    name: str = Field(..., min_length=1, max_length=100, description="机器人名称")
    chat_llm_id: int = Field(..., description="对话LLM模型ID")
    knowledge_ids: List[int] = Field(..., min_length=1, description="关联的知识库ID列表")
    system_prompt: str = Field(
        default="你是一个智能助手，请基于提供的知识库内容回答用户问题。",
        max_length=2000,
        description="系统提示词"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="检索Top-K，1-20")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度，0.0-2.0")
    max_tokens: int = Field(default=2000, ge=100, le=8000, description="最大生成Token数，100-8000")
    description: Optional[str] = Field(None, max_length=500, description="机器人描述")


# ==================== 机器人信息 ====================
class RobotBase(BaseModel):
    """机器人基础信息"""
    name: str = Field(..., description="机器人名称")
    chat_llm_id: int = Field(..., description="对话LLM模型ID")
    system_prompt: str = Field(..., description="系统提示词")
    top_k: int = Field(..., description="检索Top-K")
    temperature: float = Field(..., description="生成温度")
    max_tokens: int = Field(..., description="最大生成Token数")
    description: Optional[str] = Field(None, description="机器人描述")
    status: int = Field(..., description="状态：0-禁用，1-启用")


class RobotDetail(RobotBase):
    """机器人详细信息（响应）"""
    id: int = Field(..., description="机器人ID")
    user_id: int = Field(..., description="创建者用户ID")
    knowledge_ids: List[int] = Field(default_factory=list, description="关联的知识库ID列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class RobotUpdate(BaseModel):
    """机器人更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="机器人名称")
    chat_llm_id: Optional[int] = Field(None, description="对话LLM模型ID")
    knowledge_ids: Optional[List[int]] = Field(None, min_length=1, description="关联的知识库ID列表")
    system_prompt: Optional[str] = Field(None, max_length=2000, description="系统提示词")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="检索Top-K")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="生成温度")
    max_tokens: Optional[int] = Field(None, ge=100, le=8000, description="最大生成Token数")
    description: Optional[str] = Field(None, max_length=500, description="机器人描述")
    status: Optional[int] = Field(None, description="状态：0-禁用，1-启用")


# ==================== 机器人列表 ====================
class RobotListResponse(BaseModel):
    """机器人列表响应"""
    total: int = Field(..., description="总数")
    items: list[RobotDetail] = Field(..., description="机器人列表")


# ==================== 机器人简要信息（用于下拉选择） ====================
class RobotBrief(BaseModel):
    """机器人简要信息"""
    id: int = Field(..., description="机器人ID")
    name: str = Field(..., description="机器人名称")
    description: Optional[str] = Field(None, description="机器人描述")

    model_config = ConfigDict(from_attributes=True)
