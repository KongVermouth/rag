"""
API Key相关的Pydantic模式
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ==================== API Key创建 ====================
class APIKeyCreate(BaseModel):
    """创建API Key请求"""
    llm_id: int = Field(..., description="关联的LLM模型ID")
    alias: str = Field(..., min_length=1, max_length=100, description="密钥名称/别名")
    api_key: str = Field(..., min_length=1, max_length=500, description="API密钥（明文，将被加密存储）")
    description: Optional[str] = Field(None, max_length=500, description="密钥描述")


# ==================== API Key基础信息 ====================
class APIKeyBase(BaseModel):
    """API Key基础信息"""
    alias: str = Field(..., description="密钥名称/别名")
    description: Optional[str] = Field(None, description="密钥描述")
    status: int = Field(..., description="状态：0-禁用，1-启用")


class APIKeyDetail(BaseModel):
    """API Key详细信息（响应）- 用于管理员查看"""
    id: int = Field(..., description="API Key ID")
    llm_id: int = Field(..., description="关联的LLM模型ID")
    user_id: int = Field(..., description="创建者用户ID")
    alias: str = Field(..., description="密钥名称/别名")
    api_key_masked: str = Field(..., description="脱敏后的API Key")
    description: Optional[str] = Field(None, description="密钥描述")
    status: int = Field(..., description="状态：0-禁用，1-启用")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class APIKeyUpdate(BaseModel):
    """API Key更新请求"""
    alias: Optional[str] = Field(None, min_length=1, max_length=100, description="密钥名称/别名")
    api_key: Optional[str] = Field(None, min_length=1, max_length=500, description="新的API密钥（明文）")
    description: Optional[str] = Field(None, max_length=500, description="密钥描述")
    status: Optional[int] = Field(None, ge=0, le=1, description="状态：0-禁用，1-启用")


# ==================== API Key列表 ====================
class APIKeyListResponse(BaseModel):
    """API Key列表响应"""
    total: int = Field(..., description="总数")
    items: list[APIKeyDetail] = Field(..., description="API Key列表")


# ==================== 普通用户可用的API Key选项 ====================
class APIKeyOption(BaseModel):
    """API Key选项（供普通用户选择使用）"""
    id: int = Field(..., description="API Key ID")
    llm_id: int = Field(..., description="关联的LLM模型ID")
    llm_name: Optional[str] = Field(None, description="LLM模型名称")
    alias: str = Field(..., description="密钥名称/别名")
    
    model_config = ConfigDict(from_attributes=True)


class APIKeyOptionsResponse(BaseModel):
    """API Key选项列表响应（供普通用户使用）"""
    total: int = Field(..., description="总数")
    items: list[APIKeyOption] = Field(..., description="可用的API Key列表")


# ==================== API Key验证响应 ====================
class APIKeyValidation(BaseModel):
    """API Key验证响应"""
    is_valid: bool = Field(..., description="是否有效")
    llm_id: Optional[int] = Field(None, description="关联的LLM模型ID")
    decrypted_key: Optional[str] = Field(None, description="解密后的API Key")
