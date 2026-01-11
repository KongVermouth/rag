"""
文档管理服务
"""
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, BinaryIO
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from app.models.user import User
from app.models.document import Document
from app.models.knowledge import Knowledge
from app.schemas.document import DocumentListResponse, DocumentDetail, DocumentUploadResponse
from app.utils.storage import FileStorage
from app.core.config import settings
from app.utils.file_parser import file_parser
from app.utils.text_splitter import TextSplitter
from app.utils.embedding import get_embedding_model
from app.utils.es_client import ESClient
from app.utils.milvus_client import MilvusClient

logger = logging.getLogger(__name__)


class DocumentService:
    """文档管理服务类"""

    def __init__(self):
        self.file_storage = FileStorage()

    async def upload_document(
        self,
        db: Session,
        knowledge_id: int,
        file: UploadFile,
        current_user: User
    ) -> DocumentUploadResponse:
        """
        上传文档到知识库
        
        Args:
            db: 数据库会话
            knowledge_id: 知识库ID
            file: 上传的文件
            current_user: 当前用户
            
        Returns:
            DocumentUploadResponse: 上传响应
        """
        # 验证知识库是否存在且有权限
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="知识库不存在"
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

        # 保存文件
        try:
            # 创建临时文件对象
            import io
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
            status="uploading",  # 上传中，等待后台处理
            chunk_count=0
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # 触发文档处理任务
        task_id = None
        if settings.USE_CELERY:
            # 使用 Celery 异步处理
            from app.tasks.document_tasks import process_document_task
            task = process_document_task.delay(document.id)
            task_id = task.id
            logger.info(f"文档已提交异步处理: {file.filename} (ID: {document.id}, Task: {task_id})")
        else:
            # 使用同步处理
            logger.info(f"开始同步处理文档: {file.filename} (ID: {document.id})")
            self._process_document_sync(db, document, knowledge)

        logger.info(f"文档上传成功: {file.filename} (ID: {document.id}, Knowledge: {knowledge_id})")

        # 重新获取最新状态
        db.refresh(document)

        return DocumentUploadResponse(
            document_id=document.id,
            filename=file.filename,
            file_size=file_size,
            task_id=task_id,
            message="文档上传成功，正在后台处理" if settings.USE_CELERY else f"文档处理{'成功' if document.status == 'completed' else '失败'}"
        )

    def _process_document_sync(
        self,
        db: Session,
        document: Document,
        knowledge: Knowledge
    ) -> None:
        """
        同步处理文档：解析、切片、向量化、索引
        
        Args:
            db: 数据库会话
            document: 文档对象
            knowledge: 知识库对象
        """
        try:
            # 1. 更新状态为解析中
            document.status = "parsing"
            db.commit()
            
            # 2. 解析文档
            logger.info(f"开始解析文档: {document.file_name} (ID: {document.id})")
            file_path = Path(settings.FILE_STORAGE_PATH) / document.file_path
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            content = file_parser.parse_file(file_path)
            if not content or len(content.strip()) == 0:
                raise ValueError("文档内容为空")
            
            # 3. 文本切片
            logger.info(f"开始切片文档: {document.file_name}")
            text_splitter = TextSplitter(
                chunk_size=knowledge.chunk_size,
                chunk_overlap=knowledge.chunk_overlap
            )
            chunks = text_splitter.split_text(content)
            
            if not chunks:
                raise ValueError("文档切片失败，未生成任何切片")
            
            logger.info(f"文档切片完成，共 {len(chunks)} 个切片")
            
            # 4. 更新状态为向量化中
            document.status = "embedding"
            db.commit()
            
            # 5. 生成向量
            logger.info(f"开始向量化: {len(chunks)} 个切片")
            embedding_model = get_embedding_model()
            vectors = embedding_model.batch_encode(chunks, show_progress=False)
            
            # 6. 存储到 Milvus 和 Elasticsearch
            logger.info(f"开始存储向量和索引")
            milvus_client = MilvusClient()
            es_client = ESClient()
            
            # 准备数据
            chunk_data = []
            for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                chunk_id = f"{document.id}_{idx}"
                chunk_data.append({
                    "chunk_id": chunk_id,
                    "document_id": document.id,
                    "knowledge_id": knowledge.id,
                    "content": chunk_text,
                    "vector": vector.tolist(),
                    "chunk_index": idx,
                    "filename": document.file_name
                })
            
            # 批量插入 Milvus
            milvus_client.insert_vectors(
                collection_name=knowledge.vector_collection_name,
                data=chunk_data
            )
            logger.info(f"向量存储完成: {len(chunk_data)} 条")
            
            # 批量索引到 Elasticsearch
            es_client.batch_index_chunks(chunk_data)
            logger.info(f"ES索引完成: {len(chunk_data)} 条")
            
            # 7. 更新文档状态
            document.status = "completed"
            document.chunk_count = len(chunks)
            document.error_msg = None
            
            # 更新知识库统计
            knowledge.document_count = db.query(Document).filter(
                Document.knowledge_id == knowledge.id,
                Document.status == "completed"
            ).count()
            total_chunks_query = db.query(Document).filter(
                Document.knowledge_id == knowledge.id,
                Document.status == "completed"
            ).with_entities(Document.chunk_count).all()
            knowledge.total_chunks = sum([c[0] or 0 for c in total_chunks_query])
            
            db.commit()
            
            logger.info(f"文档处理完成: {document.file_name} (ID: {document.id})")
            
        except Exception as e:
            logger.error(f"文档处理失败: {e}", exc_info=True)
            document.status = "failed"
            document.error_msg = f"处理失败: {str(e)}"
            db.commit()

    def get_document_by_id(self, db: Session, document_id: int, current_user: User) -> Document:
        """获取文档详情"""
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )

        # 权限检查
        knowledge = db.query(Knowledge).filter(Knowledge.id == document.knowledge_id).first()
        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此文档"
            )

        return document

    def get_documents(
        self,
        db: Session,
        knowledge_id: int,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> DocumentListResponse:
        """
        获取知识库的文档列表

        Args:
            db: 数据库会话
            knowledge_id: 知识库ID
            current_user: 当前用户
            skip: 跳过记录数
            limit: 返回记录数
            keyword: 搜索关键词
            status_filter: 状态过滤

        Returns:
            DocumentListResponse: 文档列表响应
        """
        # 验证知识库权限
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="知识库不存在"
            )

        if knowledge.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此知识库"
            )

        query = db.query(Document).filter(Document.knowledge_id == knowledge_id)

        # 关键词搜索
        if keyword:
            query = query.filter(Document.file_name.ilike(f"%{keyword}%"))

        # 状态过滤
        if status_filter:
            query = query.filter(Document.status == status_filter)

        total = query.count()
        documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

        return DocumentListResponse(
            total=total,
            items=[DocumentDetail.model_validate(doc) for doc in documents]
        )

    def delete_document(self, db: Session, document_id: int, current_user: User) -> None:
        """
        删除文档
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            current_user: 当前用户
        """
        document = self.get_document_by_id(db, document_id, current_user)

        # 删除文件
        try:
            file_path = Path(settings.FILE_STORAGE_PATH) / document.file_path
            if file_path.exists():
                file_path.unlink()
                logger.info(f"删除文件: {file_path}")
        except Exception as e:
            logger.warning(f"删除文件失败: {e}")

        # 删除向量和索引
        # TODO: 删除Milvus中的向量和ES中的索引

        # 删除数据库记录
        db.delete(document)
        db.commit()

        logger.info(f"删除文档: {document.file_name} (ID: {document.id})")


# 全局文档服务实例
document_service = DocumentService()
