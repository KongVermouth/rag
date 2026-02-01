"""
文档管理服务 (异步)
"""
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from fastapi import HTTPException, status, UploadFile

from app.models.user import User
from app.models.document import Document
from app.models.knowledge import Knowledge
from app.schemas.document import DocumentListResponse, DocumentDetail, DocumentUploadResponse
from app.utils.storage import FileStorage
from app.core.config import settings
from app.kafka.producer import producer
from app.utils.milvus_client import milvus_client
from app.utils.es_client import es_client

import io
import mimetypes
from PIL import Image
try:
    import magic
except ImportError:
    magic = None

logger = logging.getLogger(__name__)


class DocumentService:
    """文档管理服务类"""

    def __init__(self):
        self.file_storage = FileStorage()

    def _get_mime_type(self, file_content: bytes, filename: str) -> str:
        """获取文件的MIME类型"""
        mime_type = None
        if magic:
            try:
                mime_type = magic.from_buffer(file_content, mime=True)
            except Exception as e:
                logger.warning(f"magic获取MIME类型失败: {e}")
        
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(filename)
        
        return mime_type or "application/octet-stream"

    def _get_image_dimensions(self, file_content: bytes) -> tuple[Optional[int], Optional[int]]:
        """获取图片宽高"""
        try:
            with Image.open(io.BytesIO(file_content)) as img:
                return img.width, img.height
        except Exception:
            return None, None

    async def upload_document(
        self,
        db: AsyncSession,
        knowledge_id: int,
        file: UploadFile,
        current_user: User
    ) -> DocumentUploadResponse:
        """
        上传文档到知识库
        """
        # 验证知识库是否存在且有权限
        result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
        knowledge = result.scalar_one_or_none()
        
        if not knowledge:
            logger.warning(f"Knowledge not found in upload_document: ID={knowledge_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"知识库 [ID={knowledge_id}] 不存在"
            )

        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此知识库"
            )

        # 验证文件类型
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = ['.pdf', '.docx', '.txt', '.md', '.html']
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(allowed_extensions)}"
            )

        # 验证文件大小
        file_content = await file.read()
        file_size = len(file_content)
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制（最大{settings.MAX_FILE_SIZE / 1024 / 1024}MB）"
            )

        # 获取MIME类型和维度
        mime_type = self._get_mime_type(file_content, file.filename)
        width, height = None, None
        if mime_type.startswith("image/"):
            width, height = self._get_image_dimensions(file_content)

        # 保存文件
        try:
            # 创建临时文件对象
            file_obj = io.BytesIO(file_content)
            # save_file 返回元组 (relative_path, file_size)
            relative_path, _ = self.file_storage.save_file(
                file=file_obj,
                original_filename=file.filename,
                knowledge_id=knowledge_id
            )
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文件保存失败"
            )

        # 创建文档记录
        document = Document(
            knowledge_id=knowledge_id,
            file_name=file.filename,
            file_extension=file_ext[1:],  # 去掉点号
            file_path=relative_path,
            file_size=file_size,
            mime_type=mime_type,
            width=width,
            height=height,
            status="uploading",  # 上传中，等待后台处理
            chunk_count=0
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        # 触发文档处理任务 (Kafka)
        try:
            await producer.send("rag.document.upload", {
                "document_id": document.id,
                "file_path": str(relative_path),
                "file_name": file.filename,
                "knowledge_id": knowledge_id
            })
            logger.info(f"文档已发送至Kafka: {file.filename} (ID: {document.id})")
        except Exception as e:
            logger.error(f"发送Kafka消息失败: {e}")

        return DocumentUploadResponse(
            document_id=document.id,
            filename=file.filename,
            file_size=file_size,
            preview_url=f"/api/v1/documents/{document.id}/preview",
            mime_type=mime_type,
            width=width,
            height=height,
            task_id=None,
            message="文档上传成功，正在后台处理"
        )

    async def retry_document(self, db: AsyncSession, document_id: int, current_user: User) -> None:
        """重试向量化失败的文档"""
        document = await self.get_document_by_id(db, document_id, current_user)
        
        # 仅允许重试状态为 failed 的文档
        if document.status != "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"当前文档状态为 {document.status}，无需重试"
            )

        # 1. 更新文档状态为重新上传中
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status="uploading", error_msg=None, updated_at=datetime.now())
        )
        await db.commit()
        await db.refresh(document)

        # 2. 重新触发文档处理任务 (从解析开始)
        try:
            await producer.send("rag.document.upload", {
                "document_id": document.id,
                "file_path": str(document.file_path),
                "file_name": document.file_name,
                "knowledge_id": document.knowledge_id
            })
            logger.info(f"文档重试任务已发送至Kafka: {document.file_name} (ID: {document.id})")
        except Exception as e:
            logger.error(f"重试发送Kafka消息失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="重试任务启动失败"
            )

    async def get_document_by_id(self, db: AsyncSession, document_id: int, current_user: User) -> Document:
        """获取文档详情"""
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )

        # 权限检查
        result = await db.execute(select(Knowledge).where(Knowledge.id == document.knowledge_id))
        knowledge = result.scalar_one_or_none()
        
        if not knowledge:
            logger.warning(f"Knowledge not found for document {document_id}: KB_ID={document.knowledge_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"所属知识库 [ID={document.knowledge_id}] 不存在"
            )
        
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此文档"
            )

        return document

    async def get_documents(
        self,
        db: AsyncSession,
        knowledge_id: int,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> DocumentListResponse:
        """获取知识库的文档列表"""
        # 验证知识库权限
        logger.info(f"Querying documents for KB ID: {knowledge_id} for user: {current_user.id}")
        # 使用 db.get() 替代 select() 以提高可靠性
        knowledge = await db.get(Knowledge, knowledge_id)
        
        if not knowledge:
            logger.warning(f"Knowledge not found in get_documents: ID={knowledge_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"知识库 [ID={knowledge_id}] 不存在"
            )

        if knowledge.user_id != current_user.id and current_user.role != "admin":
            logger.warning(f"Permission denied in get_documents for KB {knowledge_id}: user={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此知识库"
            )

        query = select(Document).where(Document.knowledge_id == knowledge_id)

        # 关键词搜索
        if keyword:
            query = query.where(Document.file_name.ilike(f"%{keyword}%"))

        # 状态过滤
        if status_filter:
            query = query.where(Document.status == status_filter)

        # 计算总数
        try:
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取文档总数失败"
            )

        # 分页查询
        try:
            query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
            result = await db.execute(query)
            documents = result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to query documents: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询文档列表失败"
            )

        return DocumentListResponse(
            total=total,
            items=[DocumentDetail.model_validate(doc) for doc in documents]
        )

    async def delete_document(self, db: AsyncSession, document_id: int, current_user: User) -> None:
        """删除文档"""
        document = await self.get_document_by_id(db, document_id, current_user)
        knowledge_id = document.knowledge_id

        # 1. 删除文件
        try:
            file_path = Path(settings.FILE_STORAGE_PATH) / document.file_path
            if file_path.exists():
                # 在 Windows 上，如果文件正在被解析器读取，unlink 可能会失败
                # 我们尝试删除，如果失败则记录警告，但继续删除数据库记录
                file_path.unlink()
                logger.info(f"删除文件成功: {file_path}")
        except Exception as e:
            logger.warning(f"删除文件失败 (可能正在被解析): {e}")

        # 2. 删除向量和索引
        try:
            # 获取知识库信息以获取 Milvus 集合名称
            result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
            knowledge = result.scalar_one_or_none()
            if knowledge:
                # 从 Milvus 删除
                await milvus_client.delete_by_document(knowledge.vector_collection_name, document_id)
                # 从 ES 删除
                await es_client.delete_by_document(document_id)
                logger.info(f"清理文档 {document_id} 的向量和索引成功")
        except Exception as e:
            logger.error(f"清理文档 {document_id} 的向量或索引失败: {e}")

        # 3. 删除数据库记录
        await db.delete(document)
        await db.commit()

        # 4. 更新知识库统计信息
        try:
            # 重新计算文档数和切片数
            doc_count_result = await db.execute(
                select(func.count(Document.id))
                .where(Document.knowledge_id == knowledge_id, Document.status == 'completed')
            )
            doc_count = doc_count_result.scalar()

            total_chunks_result = await db.execute(
                select(func.sum(Document.chunk_count))
                .where(Document.knowledge_id == knowledge_id, Document.status == 'completed')
            )
            total_chunks = total_chunks_result.scalar() or 0

            await db.execute(
                update(Knowledge)
                .where(Knowledge.id == knowledge_id)
                .values(document_count=doc_count, total_chunks=total_chunks)
            )
            await db.commit()
            logger.info(f"更新知识库 {knowledge_id} 统计信息成功")
        except Exception as e:
            logger.error(f"更新知识库统计信息失败: {e}")

        logger.info(f"删除文档成功: {document.file_name} (ID: {document.id})")


# 全局文档服务实例
document_service = DocumentService()
