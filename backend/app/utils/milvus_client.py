"""
Milvus向量数据库客户端封装
"""
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


class MilvusClient:
    """Milvus客户端封装类"""
    
    def __init__(self):
        """初始化Milvus连接"""
        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT
        )
        print(f"[OK] 连接Milvus: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    
    def _truncate_to_bytes(self, text: str, max_bytes: int) -> str:
        """
        截取字符串，确保UTF-8字节长度不超过指定值
        
        Args:
            text: 原始字符串
            max_bytes: 最大字节数
        
        Returns:
            截取后的字符串
        """
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        # 截取字节并解码，忽略不完整的字符
        return encoded[:max_bytes].decode('utf-8', errors='ignore')
    
    def create_collection(
        self,
        collection_name: str,
        dim: int,
        description: str = ""
    ) -> Collection:
        """
        创建向量集合
        
        Args:
            collection_name: 集合名称，格式: kb_{knowledge_id}_vectors
            dim: 向量维度
            description: 集合描述
        
        Returns:
            Collection对象
        """
        # 检查集合是否已存在
        if utility.has_collection(collection_name):
            return Collection(collection_name)
        
        # 定义字段
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="document_id", dtype=DataType.INT64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content_preview", dtype=DataType.VARCHAR, max_length=2000)  # 增大以支持中文
        ]
        
        schema = CollectionSchema(fields=fields, description=description)
        collection = Collection(name=collection_name, schema=schema)
        
        # 创建索引（当数据量超过1000时自动触发）
        index_params = {
            "metric_type": "IP",  # 内积相似度
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        
        print(f"[OK] 创建Milvus集合: {collection_name} (dim={dim})")
        return collection
    
    def insert_vectors(
        self,
        collection_name: str,
        data: List[Dict[str, Any]]
    ) -> bool:
        """
        批量插入向量
        
        Args:
            collection_name: 集合名称
            data: 数据列表，每项包含 chunk_id, vector, document_id, chunk_index, content 等字段
        
        Returns:
            是否成功
        """
        if not data:
            return True
            
        collection = Collection(collection_name)
        
        # 从字典列表提取各字段
        chunk_ids = [item["chunk_id"] for item in data]
        vectors = [item["vector"] for item in data]
        document_ids = [item["document_id"] for item in data]
        chunk_indices = [item["chunk_index"] for item in data]
        # 内容预览截取，确保字节长度不超过1900（留余量）
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
    
    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回结果数量
            document_ids: 可选的文档ID过滤
        
        Returns:
            匹配结果列表，包含chunk_id, distance等字段
        """
        collection = Collection(collection_name)
        collection.load()
        
        # 搜索参数
        search_params = {
            "metric_type": "IP",
            "params": {"nprobe": 128}
        }
        
        # 构建过滤表达式
        expr = None
        if document_ids:
            doc_ids_str = ",".join(map(str, document_ids))
            expr = f"document_id in [{doc_ids_str}]"
        
        # 执行搜索
        results = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "document_id", "chunk_index", "content_preview"]
        )
        
        # 格式化结果
        formatted_results = []
        for hit in results[0]:
            # IP距离归一化到0-1范围（IP范围为[-1, 1]）
            normalized_score = (hit.distance + 1) / 2
            
            formatted_results.append({
                "chunk_id": hit.entity.get("chunk_id"),
                "document_id": hit.entity.get("document_id"),
                "chunk_index": hit.entity.get("chunk_index"),
                "content_preview": hit.entity.get("content_preview"),
                "score": normalized_score
            })
        
        return formatted_results
    
    def delete_by_document(self, collection_name: str, document_id: int) -> bool:
        """
        删除指定文档的所有向量
        
        Args:
            collection_name: 集合名称
            document_id: 文档ID
        
        Returns:
            是否成功
        """
        collection = Collection(collection_name)
        expr = f"document_id == {document_id}"
        collection.delete(expr)
        collection.flush()
        return True
    
    def drop_collection(self, collection_name: str) -> bool:
        """
        删除集合
        
        Args:
            collection_name: 集合名称
        
        Returns:
            是否成功
        """
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            print(f"[OK] 删除Milvus集合: {collection_name}")
            return True
        return False
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Args:
            collection_name: 集合名称
        
        Returns:
            统计信息字典
        """
        if not utility.has_collection(collection_name):
            return {"exists": False}
        
        collection = Collection(collection_name)
        stats = collection.num_entities
        
        return {
            "exists": True,
            "num_entities": stats,
            "name": collection_name
        }
    
    def close(self):
        """关闭连接"""
        connections.disconnect("default")


# 创建全局Milvus客户端实例
milvus_client = MilvusClient()
