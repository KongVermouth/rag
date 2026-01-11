"""
文档处理异步任务
"""
import logging
from pathlib import Path
from typing import List
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.knowledge import Knowledge
from app.utils.file_parser import file_parser
from app.utils.text_splitter import TextSplitter
from app.utils.embedding import get_embedding_model
from app.utils.es_client import ESClient
from app.utils.milvus_client import MilvusClient
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="process_document")
def process_document_task(self, document_id: int):
    """
    文档处理任务：解析、切片、向量化、索引
    
    Args:
        document_id: 文档ID
        
    流程：
    1. 解析文档内容
    2. 文本切片
    3. 生成向量（Embedding）
    4. 存储向量到Milvus
    5. 存储文本到Elasticsearch
    """
    db: Session = SessionLocal()
    
    try:
        # 获取文档记录
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"文档不存在: {document_id}")
            return {"status": "error", "message": "文档不存在"}
        
        # 获取知识库配置
        knowledge = db.query(Knowledge).filter(Knowledge.id == document.knowledge_id).first()
        if not knowledge:
            logger.error(f"知识库不存在: {document.knowledge_id}")
            document.status = "failed"
            document.error_msg = "知识库不存在"
            db.commit()
            return {"status": "error", "message": "知识库不存在"}
        
        # 更新状态为解析中
        document.status = "parsing"
        db.commit()
        
        # 1. 解析文档
        logger.info(f"开始解析文档: {document.file_name} (ID: {document_id})")
        file_path = Path(settings.FILE_STORAGE_PATH) / document.file_path
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        content = file_parser.parse_file(file_path)
        if not content or len(content.strip()) == 0:
            raise ValueError("文档内容为空")
        
        # 2. 文本切片
        logger.info(f"开始切片文档: {document.file_name}")
        text_splitter = TextSplitter(
            chunk_size=knowledge.chunk_size,
            chunk_overlap=knowledge.chunk_overlap
        )
        chunks = text_splitter.split_text(content)
        
        if not chunks:
            raise ValueError("文档切片失败，未生成任何切片")
        
        logger.info(f"文档切片完成，共 {len(chunks)} 个切片")
        
        # 3. 生成向量
        logger.info(f"开始向量化: {len(chunks)} 个切片")
        embedding_model = get_embedding_model()
        vectors = embedding_model.batch_encode(chunks, show_progress=False)
        
        # 4. 存储到Milvus和Elasticsearch
        logger.info(f"开始存储向量和索引")
        milvus_client = MilvusClient()
        es_client = ESClient()
        
        # 准备数据
        chunk_data = []
        for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = f"{document_id}_{idx}"
            chunk_data.append({
                "chunk_id": chunk_id,
                "document_id": document_id,
                "knowledge_id": knowledge.id,
                "content": chunk_text,
                "vector": vector.tolist(),
                "chunk_index": idx,
                "filename": document.file_name
            })
        
        # 批量插入Milvus
        milvus_client.insert_vectors(
            collection_name=knowledge.vector_collection_name,
            data=chunk_data
        )
        logger.info(f"向量存储完成: {len(chunk_data)} 条")
        
        # 批量索引到Elasticsearch
        es_client.batch_index_chunks(chunk_data)
        logger.info(f"ES索引完成: {len(chunk_data)} 条")
        
        # 5. 更新文档状态
        document.status = "completed"
        document.chunk_count = len(chunks)
        document.error_msg = None  # 成功时清空错误信息
        
        # 更新知识库统计
        knowledge.document_count = db.query(Document).filter(
            Document.knowledge_id == knowledge.id,
            Document.status == "completed"
        ).count()
        knowledge.total_chunks = db.query(Document).filter(
            Document.knowledge_id == knowledge.id,
            Document.status == "completed"
        ).with_entities(Document.chunk_count).all()
        knowledge.total_chunks = sum([c[0] or 0 for c in knowledge.total_chunks])
        
        db.commit()
        
        logger.info(f"文档处理完成: {document.file_name} (ID: {document_id})")
        
        return {
            "status": "success",
            "document_id": document_id,
            "chunk_count": len(chunks),
            "message": "文档处理成功"
        }
        
    except Exception as e:
        logger.error(f"文档处理失败: {e}", exc_info=True)
        
        # 更新状态为失败
        if document:
            document.status = "failed"
            document.error_msg = f"处理失败: {str(e)}"
            db.commit()
        
        return {
            "status": "error",
            "document_id": document_id,
            "message": str(e)
        }
        
    finally:
        db.close()


@celery_app.task(name="batch_process_documents")
def batch_process_documents_task(document_ids: List[int]):
    """
    批量处理文档任务
    
    Args:
        document_ids: 文档ID列表
    """
    results = []
    for doc_id in document_ids:
        result = process_document_task.delay(doc_id)
        results.append({
            "document_id": doc_id,
            "task_id": result.id
        })
    
    return {
        "status": "success",
        "message": f"已提交 {len(document_ids)} 个文档处理任务",
        "tasks": results
    }


@celery_app.task(name="cleanup_failed_documents")
def cleanup_failed_documents_task():
    """
    清理失败的文档（定时任务）
    
    清理超过7天的失败文档记录
    """
    from datetime import datetime, timedelta
    
    db: Session = SessionLocal()
    try:
        # 查找7天前失败的文档
        cutoff_date = datetime.now() - timedelta(days=7)
        failed_docs = db.query(Document).filter(
            Document.status == "failed",
            Document.updated_at < cutoff_date
        ).all()
        
        deleted_count = 0
        for doc in failed_docs:
            # 删除文件
            try:
                file_path = Path(settings.FILE_STORAGE_PATH) / doc.file_path
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"删除文件失败: {e}")
            
            # 删除记录
            db.delete(doc)
            deleted_count += 1
        
        db.commit()
        
        logger.info(f"清理失败文档完成，共删除 {deleted_count} 个文档")
        return {
            "status": "success",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"清理失败文档出错: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        db.close()
