import asyncio
import logging
import sys
import os
from sqlalchemy import select, update, func

sys.path.append(os.getcwd())

from app.kafka.consumer import KafkaConsumer
from app.utils.embedding import get_embedding_model, RemoteEmbeddingClient
from app.core.exceptions import VectorizationFailedException
from app.utils.milvus_client import milvus_client
from app.utils.es_client import es_client
from app.db.session import AsyncSessionLocal
from app.models.document import Document
from app.models.knowledge import Knowledge
from app.models.llm import LLM
from app.models.apikey import APIKey
from app.core.security import api_key_crypto
from app.core.worker_logger import get_worker_logger
from app.core.llm.factory import LLMFactory

logger = get_worker_logger("vectorizer")

async def process_chunks(data: dict):
    doc_id = data.get("document_id")
    chunks = data.get("chunks")
    knowledge_id = data.get("knowledge_id")
    file_name = data.get("file_name")
    
    logger.info(f"开始执行向量化任务: doc_id={doc_id}, chunks_count={len(chunks)}")
    
    try:
        # 初始检查
        async with AsyncSessionLocal() as db:
            doc_result = await db.execute(select(Document).where(Document.id == doc_id))
            if not doc_result.scalar_one_or_none():
                logger.warning(f"文档不存在，跳过处理: doc_id={doc_id}")
                return

            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="embedding")
            )
            await db.commit()
            logger.debug(f"文档状态已更新为向量化中: doc_id={doc_id}")
        
        # 1. 获取 Embedding 模型配置和知识库信息
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
            knowledge = result.scalar_one_or_none()
            
            if not knowledge:
                logger.error(f"知识库未找到: knowledge_id={knowledge_id}")
                return
            
            collection_name = knowledge.vector_collection_name
            logger.debug(f"目标向量集合: {collection_name}")
            
            llm = None
            if knowledge.embed_llm_id:
                llm_result = await db.execute(select(LLM).where(LLM.id == knowledge.embed_llm_id))
                llm = llm_result.scalar_one_or_none()
            
            if llm and llm.base_url:
                # 使用远程 API (使用统一抽象层)
                logger.info(f"使用远程 Embedding 模型: {llm.model_name}")
                # 获取 API Key
                ak_stmt = select(APIKey).where(APIKey.llm_id == llm.id, APIKey.status == 1)
                ak_result = await db.execute(ak_stmt)
                apikey = ak_result.scalar_one_or_none()
                api_key = api_key_crypto.decrypt(apikey.api_key_encrypted) if apikey else ""
                
                provider = LLMFactory.get_provider(
                    provider_name=llm.provider,
                    api_key=api_key,
                    base_url=llm.base_url,
                    api_version=llm.api_version
                )
                
                vectors_list = await provider.embed(chunks, llm.model_name)
                import numpy as np
                vectors = [np.array(v) for v in vectors_list]
            else:
                # 使用本地模型
                logger.info("使用本地 Embedding 模型")
                embedding_model = get_embedding_model()
                loop = asyncio.get_running_loop()
                vectors = await loop.run_in_executor(None, lambda: embedding_model.batch_encode(chunks, show_progress=False))
        
        logger.debug(f"向量生成完成: doc_id={doc_id}")

        # 2. 存储数据
        chunk_data = []
        for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = f"{doc_id}_{idx}"
            chunk_data.append({
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "knowledge_id": knowledge_id,
                "content": chunk_text,
                "vector": vector.tolist(),
                "chunk_index": idx,
                "file_name": file_name
            })
            
        # Milvus 存储
        logger.debug(f"正在存入 Milvus: doc_id={doc_id}")
        await milvus_client.insert_vectors(
            collection_name=collection_name,
            data=chunk_data
        )
        
        # ES 存储
        logger.debug(f"正在存入 Elasticsearch: doc_id={doc_id}")
        await es_client.batch_index_chunks(chunk_data)
        
        # 3. 更新数据库
        async with AsyncSessionLocal() as db:
            # 再次检查文档是否存在
            doc_result = await db.execute(select(Document).where(Document.id == doc_id))
            if not doc_result.scalar_one_or_none():
                logger.warning(f"文档在向量化过程中被删除，正在清理资源: doc_id={doc_id}")
                await milvus_client.delete_by_document(collection_name, doc_id)
                await es_client.delete_by_document(doc_id)
                return

            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="completed", chunk_count=len(chunks), error_msg=None)
            )
            
            # 重新计算知识库统计信息
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
            
        logger.info(f"文档处理全部完成: doc_id={doc_id}, 总计 {len(chunks)} 个切片")

    except VectorizationFailedException as e:
        logger.error(f"向量化业务失败: doc_id={doc_id}, message={e.message}, detail={e.detail}, trace_id={e.trace_id}")
        error_msg = f"{e.message}"
        if e.detail:
            error_msg += f" (详情: {e.detail})"
        
        # 清理可能已经写入的部分数据 (原子性保证)
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
                knowledge = result.scalar_one_or_none()
                if knowledge:
                    await milvus_client.delete_by_document(knowledge.vector_collection_name, doc_id)
                    await es_client.delete_by_document(doc_id)
                    logger.info(f"由于向量化失败，已清理文档 {doc_id} 的部分向量和索引数据")
        except Exception as cleanup_err:
            logger.error(f"清理部分数据失败: {cleanup_err}")

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="failed", error_msg=error_msg)
            )
            await db.commit()
        logger.error(f"文档状态已更新为失败: doc_id={doc_id}")

    except Exception as e:
        logger.exception(f"向量化过程中发生未知异常: doc_id={doc_id}, error={str(e)}")
        # 清理可能已经写入的部分数据 (原子性保证)
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
                knowledge = result.scalar_one_or_none()
                if knowledge:
                    await milvus_client.delete_by_document(knowledge.vector_collection_name, doc_id)
                    await es_client.delete_by_document(doc_id)
                    logger.info(f"由于未知异常，已清理文档 {doc_id} 的部分向量和索引数据")
        except Exception as cleanup_err:
            logger.error(f"清理部分数据失败: {cleanup_err}")
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(status="failed", error_msg=f"向量化失败: {str(e)}")
            )
            await db.commit()
        logger.error(f"文档状态已更新为失败: doc_id={doc_id}")

async def heartbeat():
    """心跳日志，证明 Worker 存活"""
    while True:
        logger.info("Vectorizer Worker 心跳正常，等待任务中...")
        await asyncio.sleep(60)

async def main():
    logger.info("Vectorizer Worker 正在启动...")
    consumer = KafkaConsumer(
        "rag.document.chunks", 
        "vectorizer_group", 
        process_chunks
    )
    try:
        # 启动消费者以及心跳任务
        await asyncio.gather(
            consumer.start(),
            heartbeat()
        )
    except Exception as e:
        logger.critical(f"Vectorizer Worker 运行异常并退出: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
