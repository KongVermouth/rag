import asyncio
import logging
import sys
import os
from sqlalchemy import select, update

sys.path.append(os.getcwd())

from app.kafka.consumer import KafkaConsumer
from app.kafka.producer import producer
from app.utils.text_splitter import TextSplitter
from app.db.session import AsyncSessionLocal
from app.models.document import Document
from app.models.knowledge import Knowledge
from app.core.config import settings
from app.core.worker_logger import get_worker_logger

logger = get_worker_logger("splitter")

async def process_parsed(data: dict):
    doc_id = data.get("document_id")
    content = data.get("content")
    knowledge_id = data.get("knowledge_id")
    file_name = data.get("file_name")
    
    logger.info(f"开始执行文档切片任务: doc_id={doc_id}, file_name={file_name}")
    
    try:
        # 更新状态为切片中
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="splitting")
            )
            await db.commit()
            logger.debug(f"文档状态已更新为切片中: doc_id={doc_id}")

        # 检查文档是否存在并获取知识库配置
        async with AsyncSessionLocal() as db:
            doc_result = await db.execute(select(Document).where(Document.id == doc_id))
            if not doc_result.scalar_one_or_none():
                logger.warning(f"文档不存在，跳过处理: doc_id={doc_id}")
                return

            result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
            knowledge = result.scalar_one_or_none()
            
            if not knowledge:
                raise ValueError(f"关联的知识库未找到: knowledge_id={knowledge_id}")
                
            chunk_size = knowledge.chunk_size or settings.DEFAULT_CHUNK_SIZE
            chunk_overlap = knowledge.chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
            logger.debug(f"切片配置: chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")

        # 更新切片器配置
        splitter = TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        # 执行切片
        chunks = splitter.split_text(content)
        
        if not chunks:
            raise ValueError("未生成任何切片内容")
            
        logger.info(f"文档切片成功: doc_id={doc_id}, chunks_count={len(chunks)}")
        
        # 发送到下一阶段 (vectorizer)
        await producer.send("rag.document.chunks", {
            "document_id": doc_id,
            "chunks": chunks,
            "knowledge_id": knowledge_id,
            "file_name": file_name
        })
        logger.info(f"切片内容已发送至 Kafka: doc_id={doc_id}")

    except Exception as e:
        logger.exception(f"文档切片时发生异常: doc_id={doc_id}, error={str(e)}")
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="failed", error_msg=f"切片失败: {str(e)}")
            )
            await db.commit()
        logger.error(f"文档状态已更新为失败: doc_id={doc_id}")

async def heartbeat():
    """心跳日志，证明 Worker 存活"""
    while True:
        logger.info("Splitter Worker 心跳正常，等待任务中...")
        await asyncio.sleep(60)

async def main():
    logger.info("Splitter Worker 正在启动...")
    consumer = KafkaConsumer(
        "rag.document.parsed", 
        "splitter_group", 
        process_parsed
    )
    try:
        # 启动消费者、生产者以及心跳任务
        await asyncio.gather(
            consumer.start(), 
            producer.start(),
            heartbeat()
        )
    except Exception as e:
        logger.critical(f"Splitter Worker 运行异常并退出: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
