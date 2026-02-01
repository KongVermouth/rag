"""
Milvus向量数据库客户端封装 (异步封装)
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus客户端封装类 (异步封装)"""
    
    def __init__(self):
        """初始化Milvus连接"""
        # 建立同步连接
        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT
        )
        logger.info(f"连接Milvus: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    
    def _truncate_to_bytes(self, text: str, max_bytes: int) -> str:
        """
        截取字符串，确保UTF-8字节长度不超过指定值
        """
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        return encoded[:max_bytes].decode('utf-8', errors='ignore')
    
    async def create_collection(
        self,
        collection_name: str,
        dim: int,
        description: str = ""
    ) -> Collection:
        """
        创建向量集合 (异步)
        """
        return await asyncio.to_thread(self._create_collection_sync, collection_name, dim, description)

    def _create_collection_sync(self, collection_name: str, dim: int, description: str) -> Collection:
        # 检查集合是否已存在
        if utility.has_collection(collection_name):
            return Collection(collection_name)
        
        # 定义字段
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="document_id", dtype=DataType.INT64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content_preview", dtype=DataType.VARCHAR, max_length=2000)
        ]
        
        schema = CollectionSchema(fields=fields, description=description)
        collection = Collection(name=collection_name, schema=schema)
        
        # 创建索引
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        
        logger.info(f"创建Milvus集合: {collection_name} (dim={dim})")
        return collection
    
    async def insert_vectors(
        self,
        collection_name: str,
        data: List[Dict[str, Any]]
    ) -> bool:
        """
        批量插入向量 (异步)
        """
        if not data:
            return True
        return await asyncio.to_thread(self._insert_vectors_sync, collection_name, data)

    def _insert_vectors_sync(self, collection_name: str, data: List[Dict[str, Any]]) -> bool:
        collection = Collection(collection_name)
        
        chunk_ids = [item["chunk_id"] for item in data]
        vectors = [item["vector"] for item in data]
        document_ids = [item["document_id"] for item in data]
        chunk_indices = [item["chunk_index"] for item in data]
        content_previews = [self._truncate_to_bytes(item["content"], 1900) for item in data]
        
        insert_data = [
            chunk_ids,
            vectors,
            document_ids,
            chunk_indices,
            content_previews
        ]
        
        collection.insert(insert_data)
        collection.flush()
        return True
    
    async def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索 (异步)
        """
        return await asyncio.to_thread(self._search_vectors_sync, collection_name, query_vector, top_k, document_ids)

    def _search_vectors_sync(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        collection = Collection(collection_name)
        collection.load()
        
        search_params = {
            "metric_type": "IP",
            "params": {"nprobe": 128}
        }
        
        expr = None
        if document_ids:
            doc_ids_str = ",".join(map(str, document_ids))
            expr = f"document_id in [{doc_ids_str}]"
        
        results = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "document_id", "chunk_index", "content_preview"]
        )
        
        formatted_results = []
        for hit in results[0]:
            normalized_score = (hit.distance + 1) / 2
            formatted_results.append({
                "chunk_id": hit.entity.get("chunk_id"),
                "document_id": hit.entity.get("document_id"),
                "chunk_index": hit.entity.get("chunk_index"),
                "content_preview": hit.entity.get("content_preview"),
                "score": normalized_score
            })
        
        return formatted_results
    
    async def delete_by_document(self, collection_name: str, document_id: int) -> bool:
        """
        删除指定文档的所有向量 (异步)
        """
        return await asyncio.to_thread(self._delete_by_document_sync, collection_name, document_id)

    def _delete_by_document_sync(self, collection_name: str, document_id: int) -> bool:
        collection = Collection(collection_name)
        expr = f"document_id == {document_id}"
        collection.delete(expr)
        collection.flush()
        return True
    
    async def drop_collection(self, collection_name: str) -> bool:
        """
        删除集合 (异步)
        """
        return await asyncio.to_thread(self._drop_collection_sync, collection_name)

    def _drop_collection_sync(self, collection_name: str) -> bool:
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            logger.info(f"删除Milvus集合: {collection_name}")
            return True
        return False
    
    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取集合统计信息 (异步)
        """
        return await asyncio.to_thread(self._get_collection_stats_sync, collection_name)

    def _get_collection_stats_sync(self, collection_name: str) -> Dict[str, Any]:
        if not utility.has_collection(collection_name):
            return {"exists": False}
        
        collection = Collection(collection_name)
        stats = collection.num_entities
        
        return {
            "exists": True,
            "num_entities": stats,
            "name": collection_name
        }
    
    async def close(self):
        """关闭连接 (异步封装)"""
        await asyncio.to_thread(connections.disconnect, "default")


# 创建全局Milvus客户端实例
milvus_client = MilvusClient()
