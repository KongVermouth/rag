import asyncio
import logging
import sys
import os
from sqlalchemy import select

sys.path.append(os.getcwd())

from app.kafka.consumer import KafkaConsumer
from app.db.session import AsyncSessionLocal
from app.services.recall_service import recall_service
from app.core.worker_logger import get_worker_logger

logger = get_worker_logger("recall")

async def process_recall_test(data: dict):
    task_id = data.get("task_id")
    queries = data.get("queries")
    topN = data.get("topN")
    threshold = data.get("threshold")
    knowledge_ids = data.get("knowledge_ids")
    robot_id = data.get("robot_id")
    
    logger.info(f"收到召回测试任务: task_id={task_id}, queries_count={len(queries)}")
    
    try:
        async with AsyncSessionLocal() as db:
            await recall_service.run_recall_task(
                db=db,
                task_id=task_id,
                queries=queries,
                topN=topN,
                threshold=threshold,
                knowledge_ids=knowledge_ids,
                robot_id=robot_id
            )
        logger.info(f"召回测试任务处理完成: task_id={task_id}")
    except Exception as e:
        logger.exception(f"处理召回测试任务时发生异常: task_id={task_id}, error={e}")

async def heartbeat():
    """心跳日志"""
    while True:
        logger.info("Recall Worker 心跳正常，等待任务中...")
        await asyncio.sleep(60)

async def main():
    logger.info("Recall Worker 正在启动...")
    consumer = KafkaConsumer(
        "rag.recall.test", 
        "recall_group", 
        process_recall_test
    )
    try:
        await asyncio.gather(
            consumer.start(),
            heartbeat()
        )
    except Exception as e:
        logger.critical(f"Recall Worker 运行异常并退出: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
