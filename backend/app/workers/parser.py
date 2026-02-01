import asyncio
import logging
import sys
import os
from pathlib import Path
from sqlalchemy import select, update

# Add backend to path to allow imports
sys.path.append(os.getcwd())

from app.kafka.consumer import KafkaConsumer
from app.kafka.producer import producer
from app.utils.file_parser import file_parser
from app.db.session import AsyncSessionLocal
from app.models.document import Document
from app.core.config import settings
from app.core.worker_logger import get_worker_logger

logger = get_worker_logger("parser")

async def process_upload(data: dict):
    doc_id = data.get("document_id")
    file_path_str = data.get("file_path")
    knowledge_id = data.get("knowledge_id")
    file_name = data.get("file_name")
    
    logger.info(f"开始处理文档解析任务: doc_id={doc_id}, file_name={file_name}")
    
    # 检查文档是否存在并更新状态
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            document = result.scalar_one_or_none()
            if not document:
                logger.warning(f"文档不存在，跳过处理: doc_id={doc_id}")
                return

            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="parsing", error_msg=None)
            )
            await db.commit()
            logger.debug(f"文档状态已更新为解析中: doc_id={doc_id}")

        full_path = Path(settings.FILE_STORAGE_PATH) / file_path_str
        logger.debug(f"解析文件路径: {full_path}")
        
        # 执行解析 (线程池中执行同步操作)
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(None, file_parser.parse_file, full_path)
        
        if not content:
            raise ValueError("解析后的内容为空")

        # 发送到下一阶段 (splitter)
        await producer.send("rag.document.parsed", {
            "document_id": doc_id,
            "content": content,
            "knowledge_id": knowledge_id,
            "file_name": file_name
        })
        
        # 更新状态为已解析，准备切片
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="parsing") # 保持 parsing 状态，但在日志中记录
            )
            await db.commit()
            
        logger.info(f"文档解析完成并已发送至 Kafka: doc_id={doc_id}, content_len={len(content)}")

    except Exception as e:
        logger.exception(f"解析文档时发生异常: doc_id={doc_id}, error={str(e)}")
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="failed", error_msg=f"解析失败: {str(e)}")
            )
            await db.commit()
        logger.error(f"文档状态已更新为失败: doc_id={doc_id}")

async def heartbeat():
    """心跳日志，证明 Worker 存活"""
    while True:
        logger.info("Parser Worker 心跳正常，等待任务中...")
        await asyncio.sleep(60)

async def main():
    logger.info("Parser Worker 正在启动...")
    consumer = KafkaConsumer(
        "rag.document.upload", 
        "parser_group", 
        process_upload
    )
    try:
        # 启动消费者、生产者以及心跳任务
        await asyncio.gather(
            consumer.start(), 
            producer.start(),
            heartbeat()
        )
    except Exception as e:
        logger.critical(f"Parser Worker 运行异常并退出: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
