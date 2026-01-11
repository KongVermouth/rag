"""
知识库相关的Pydantic模式
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ==================== 知识库创建 ====================
class KnowledgeCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    embed_llm_id: int = Field(..., description="Embedding模型ID")
    chunk_size: int = Field(default=500, ge=100, le=2000, description="文本切片大小，100-2000")
    chunk_overlap: int = Field(default=50, ge=0, le=500, description="文本切片重叠，0-500")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")


# ==================== 知识库信息 ====================
class KnowledgeBase(BaseModel):
    """知识库基础信息"""
    name: str = Field(..., description="知识库名称")
    embed_llm_id: int = Field(..., description="Embedding模型ID")
    chunk_size: int = Field(..., description="文本切片大小")
    chunk_overlap: int = Field(..., description="文本切片重叠")
    description: Optional[str] = Field(None, description="知识库描述")
    status: int = Field(..., description="状态：0-禁用，1-启用")


class KnowledgeDetail(KnowledgeBase):
    """知识库详细信息（响应）"""
    id: int = Field(..., description="知识库ID")
    user_id: int = Field(..., description="创建者用户ID")
    vector_collection_name: str = Field(..., description="Milvus集合名称")
    document_count: int = Field(default=0, description="文档数量")
    total_chunks: int = Field(default=0, description="总切片数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class KnowledgeUpdate(BaseModel):
    """知识库更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    status: Optional[int] = Field(None, description="状态：0-禁用，1-启用")


# ==================== 知识库列表 ====================
class KnowledgeListResponse(BaseModel):
    """知识库列表响应"""
    total: int = Field(..., description="总数")
    items: list[KnowledgeDetail] = Field(..., description="知识库列表")


# ==================== 知识库统计信息 ====================
class KnowledgeStats(BaseModel):
    """知识库统计信息"""
    knowledge_id: int = Field(..., description="知识库ID")
    document_count: int = Field(..., description="文档数量")
    total_chunks: int = Field(..., description="总切片数")
    total_size: int = Field(..., description="文件总大小（字节）")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")


# ==================== 知识库简要信息（用于下拉选择） ====================
class KnowledgeBrief(BaseModel):
    """知识库简要信息"""
    id: int = Field(..., description="知识库ID")
    name: str = Field(..., description="知识库名称")
    document_count: int = Field(..., description="文档数量")

    model_config = ConfigDict(from_attributes=True)
