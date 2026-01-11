"""
文档管理API路由
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import DocumentListResponse, DocumentDetail, DocumentUploadResponse
from app.services.document_service import document_service
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, summary="上传文档")
async def upload_document(
    knowledge_id: int = Query(..., description="知识库ID"),
    file: UploadFile = File(..., description="上传的文件"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传文档到指定知识库
    
    支持的文件格式：PDF, DOCX, TXT, MD, HTML
    
    文件上传后会异步处理（解析、切片、向量化、索引）
    """
    return await document_service.upload_document(db, knowledge_id, file, current_user)


@router.get("", response_model=DocumentListResponse, summary="获取文档列表")
def get_documents(
    knowledge_id: int = Query(..., description="知识库ID"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    keyword: str = Query(None, description="搜索关键词"),
    status_filter: str = Query(None, description="状态过滤（pending/processing/completed/failed）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定知识库的文档列表
    """
    return document_service.get_documents(
        db, knowledge_id, current_user, skip, limit, keyword, status_filter
    )


@router.get("/{document_id}", response_model=DocumentDetail, summary="获取文档详情")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定文档的详细信息
    """
    document = document_service.get_document_by_id(db, document_id, current_user)
    return DocumentDetail.model_validate(document)


@router.delete("/{document_id}", summary="删除文档")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除文档
    
    会同时删除文件、向量和索引
    """
    document_service.delete_document(db, document_id, current_user)
    return {"message": "文档删除成功"}


@router.get("/{document_id}/status", summary="获取文档处理状态")
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档的处理状态
    
    用于前端轮询查询文档处理进度
    """
    document = document_service.get_document_by_id(db, document_id, current_user)
    return {
        "document_id": document.id,
        "file_name": document.file_name,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "error_msg": document.error_msg
    }
