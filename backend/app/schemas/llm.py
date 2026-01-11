"""
LLM模型相关的Pydantic模式
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ==================== LLM创建 ====================
class LLMCreate(BaseModel):
    """创建LLM模型请求"""
    model_config = ConfigDict(protected_namespaces=())
    
    name: str = Field(..., min_length=1, max_length=100, description="模型名称")
    model_type: str = Field(..., description="模型类型：embedding/chat")
    provider: str = Field(..., max_length=50, description="提供商：local/openai/azure等")
    model_name: str = Field(..., max_length=100, description="模型标识")
    base_url: Optional[str] = Field(None, max_length=255, description="API基础URL")
    api_version: Optional[str] = Field(None, max_length=50, description="API版本")
    description: Optional[str] = Field(None, max_length=500, description="模型描述")


# ==================== LLM信息 ====================
class LLMBase(BaseModel):
    """LLM基础信息"""
    model_config = ConfigDict(protected_namespaces=())
    
    name: str = Field(..., description="模型名称")
    model_type: str = Field(..., description="模型类型：embedding/chat")
    provider: str = Field(..., description="提供商")
    model_name: str = Field(..., description="模型标识")
    base_url: Optional[str] = Field(None, description="API基础URL")
    api_version: Optional[str] = Field(None, description="API版本")
    description: Optional[str] = Field(None, description="模型描述")
    status: int = Field(..., description="状态：0-禁用，1-启用")


class LLMDetail(LLMBase):
    """LLM详细信息（响应）"""
    id: int = Field(..., description="LLM ID")
    user_id: int = Field(..., description="创建者用户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class LLMUpdate(BaseModel):
    """LLM更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="模型名称")
    base_url: Optional[str] = Field(None, max_length=255, description="API基础URL")
    api_version: Optional[str] = Field(None, max_length=50, description="API版本")
    description: Optional[str] = Field(None, max_length=500, description="模型描述")
    status: Optional[int] = Field(None, description="状态：0-禁用，1-启用")


# ==================== LLM列表 ====================
class LLMListResponse(BaseModel):
    """LLM列表响应"""
    total: int = Field(..., description="总数")
    items: list[LLMDetail] = Field(..., description="LLM列表")


# ==================== LLM简要信息（用于下拉选择） ====================
class LLMBrief(BaseModel):
    """LLM简要信息"""
    id: int = Field(..., description="LLM ID")
    name: str = Field(..., description="模型名称")
    model_type: str = Field(..., description="模型类型")
    provider: str = Field(..., description="提供商")

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
