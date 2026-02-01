"""
文档相关的Pydantic模式
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ==================== 文档上传响应 ====================
class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    document_id: int = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    preview_url: Optional[str] = Field(None, description="预览URL")
    mime_type: Optional[str] = Field(None, description="MIME类型")
    width: Optional[int] = Field(None, description="宽度")
    height: Optional[int] = Field(None, description="高度")
    task_id: Optional[str] = Field(None, description="异步处理任务ID（同步模式下为空）")
    message: str = Field(default="文档上传成功，正在后台处理", description="提示信息")


# ==================== 文档信息 ====================
class DocumentBase(BaseModel):
    """文档基础信息"""
    file_name: str = Field(..., description="文件名")
    file_extension: str = Field(..., description="文件类型/后缀")
    file_size: int = Field(..., description="文件大小（字节）")
    status: str = Field(..., description="处理状态：uploading/parsing/embedding/completed/failed")


class DocumentDetail(DocumentBase):
    """文档详细信息（响应）"""
    id: int = Field(..., description="文档ID")
    knowledge_id: int = Field(..., description="所属知识库ID")
    file_path: str = Field(..., description="文件存储路径")
    mime_type: Optional[str] = Field(None, description="MIME类型")
    width: Optional[int] = Field(None, description="宽度")
    height: Optional[int] = Field(None, description="高度")
    preview_url: Optional[str] = Field(None, description="预览URL")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    chunk_count: int = Field(default=0, description="切片数量")
    error_msg: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = ConfigDict(from_attributes=True)


# ==================== 文档列表 ====================
class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int = Field(..., description="总数")
    items: list[DocumentDetail] = Field(..., description="文档列表")


# ==================== 文档处理状态 ====================
class DocumentProcessStatus(BaseModel):
    """文档处理状态"""
    document_id: int = Field(..., description="文档ID")
    status: str = Field(..., description="处理状态")
    progress: int = Field(default=0, ge=0, le=100, description="处理进度（0-100）")
    chunk_count: int = Field(default=0, description="已处理切片数")
    error_message: Optional[str] = Field(None, description="错误信息")


# ==================== 文档切片信息 ====================
class ChunkInfo(BaseModel):
    """文档切片信息"""
    chunk_id: str = Field(..., description="切片ID")
    content: str = Field(..., description="切片内容")
    document_id: int = Field(..., description="所属文档ID")
    chunk_index: int = Field(..., description="切片序号")
    score: Optional[float] = Field(None, description="检索相似度分数")


class ChunkListResponse(BaseModel):
    """文档切片列表响应"""
    document_id: int = Field(..., description="文档ID")
    total: int = Field(..., description="切片总数")
    items: list[ChunkInfo] = Field(..., description="切片列表")


# ==================== 批量删除文档 ====================
class DocumentBatchDelete(BaseModel):
    """批量删除文档请求"""
    document_ids: List[int] = Field(..., min_length=1, description="文档ID列表")
