"""
文档管理API路由
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import io
from PIL import Image

from app.db.session import get_db
from app.schemas.document import DocumentListResponse, DocumentDetail, DocumentUploadResponse
from app.services.document_service import document_service
from app.core.deps import get_current_user
from app.models.user import User
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, summary="上传文档")
async def upload_document(
    knowledge_id: int = Query(..., description="知识库ID"),
    file: UploadFile = File(..., description="上传的文件"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传文档到指定知识库
    
    支持的文件格式：PDF, DOCX, TXT, MD, HTML
    
    文件上传后会异步处理（解析、切片、向量化、索引）
    """
    return await document_service.upload_document(db, knowledge_id, file, current_user)


@router.get("", response_model=DocumentListResponse, summary="获取文档列表")
async def get_documents(
    knowledge_id: int = Query(..., description="知识库ID"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    keyword: str = Query(None, description="搜索关键词"),
    status_filter: str = Query(None, description="状态过滤（pending/processing/completed/failed）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定知识库的文档列表
    """
    return await document_service.get_documents(
        db, knowledge_id, current_user, skip, limit, keyword, status_filter
    )


@router.get("/{document_id}", response_model=DocumentDetail, summary="获取文档详情")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定文档的详细信息
    """
    document = await document_service.get_document_by_id(db, document_id, current_user)
    return DocumentDetail.model_validate(document)


@router.delete("/{document_id}", summary="删除文档")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除文档
    
    会同时删除文件、向量和索引
    """
    await document_service.delete_document(db, document_id, current_user)
    return {"message": "文档删除成功"}


@router.post("/{document_id}/retry", summary="重试文档处理")
async def retry_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试处理失败的文档
    
    返回格式统一为 {code, message, data}，HTTP 状态码始终为 200
    """
    try:
        await document_service.retry_document(db, document_id, current_user)
        return {
            "code": 200,
            "message": "重试任务已启动",
            "data": {"document_id": document_id}
        }
    except Exception as e:
        logger.error(f"重试文档 {document_id} 失败: {e}")
        return {
            "code": 500,
            "message": f"重试启动失败: {str(e)}",
            "data": None
        }


@router.get("/{document_id}/preview", summary="预览文档")
async def preview_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    预览文档：支持图片、PDF、视频、Office等
    """
    document = await document_service.get_document_by_id(db, document_id, current_user)
    file_path = Path(settings.FILE_STORAGE_PATH) / document.file_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 设置缓存头
    from urllib.parse import quote
    encoded_filename = quote(document.file_name)
    headers = {
        "Cache-Control": "public, max-age=86400",
        "Content-Disposition": f"inline; filename=\"{encoded_filename}\"; filename*=utf-8''{encoded_filename}"
    }
    
    return FileResponse(
        path=file_path,
        media_type=document.mime_type,
        headers=headers
    )


@router.get("/{document_id}/thumb", summary="获取缩略图")
async def get_thumbnail(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取图片或视频的缩略图 (200px)
    """
    document = await document_service.get_document_by_id(db, document_id, current_user)
    file_path = Path(settings.FILE_STORAGE_PATH) / document.file_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 仅支持图片缩略图 (视频暂不实现，返回占位图)
    if not document.mime_type or not document.mime_type.startswith("image/"):
        # 返回默认占位图逻辑
        return {"message": "仅支持图片缩略图"}

    try:
        # 生成缩略图
        img = Image.open(file_path)
        img.thumbnail((200, 200))
        
        # 将图片保存到内存中
        img_byte_arr = io.BytesIO()
        # 保持原格式或使用 JPEG
        format = img.format or 'JPEG'
        img.save(img_byte_arr, format=format)
        img_byte_arr.seek(0)
        
        return StreamingResponse(
            img_byte_arr,
            media_type=f"image/{format.lower()}",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    except Exception as e:
        logger.error(f"生成缩略图失败: {e}")
        # 失败时返回占位图 (这里简单返回 400 或 415)
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="无法生成缩略图")


@router.get("/{document_id}/status", summary="获取文档处理状态")
async def get_document_status(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档的处理状态
    
    用于前端轮询查询文档处理进度
    """
    document = await document_service.get_document_by_id(db, document_id, current_user)
    return {
        "document_id": document.id,
        "file_name": document.file_name,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "error_msg": document.error_msg
    }
