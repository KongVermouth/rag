"""
Elasticsearch客户端封装
"""
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from app.core.config import settings


class ESClient:
    """Elasticsearch客户端封装类"""
    
    def __init__(self):
        self.client = Elasticsearch([settings.ES_HOST])
        self.index_name = settings.ES_INDEX_NAME
        self._ensure_index()
    
    def _ensure_index(self):
        """确保索引存在，如不存在则创建"""
        if not self.client.indices.exists(index=self.index_name):
            self._create_index()
    
    def _create_index(self):
        """创建文档切片索引"""
        mapping = {
            "settings": {
                "number_of_shards": 3,
                "number_of_replicas": 1,
                "refresh_interval": "5s",
                "analysis": {
                    "analyzer": {
                        "ik_max_word_analyzer": {
                            "type": "custom",
                            "tokenizer": "ik_max_word"
                        },
                        "ik_smart_analyzer": {
                            "type": "custom",
                            "tokenizer": "ik_smart"
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "chunk_id": {
                        "type": "keyword"
                    },
                    "document_id": {
                        "type": "long"
                    },
                    "knowledge_id": {
                        "type": "long"
                    },
                    "chunk_index": {
                        "type": "integer"
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "file_name": {"type": "keyword"},
                            "page_number": {"type": "integer"},
                            "heading": {
                                "type": "text",
                                "analyzer": "ik_smart"
                            }
                        }
                    },
                    "char_count": {
                        "type": "integer"
                    },
                    "created_at": {
                        "type": "date"
                    }
                }
            }
        }
        
        self.client.indices.create(index=self.index_name, body=mapping)
        print(f"[OK] 创建ES索引: {self.index_name}")
    
    def index_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        批量索引文档切片
        
        Args:
            chunks: 切片数据列表，每个切片包含chunk_id, content等字段
        
        Returns:
            是否成功
        """
        actions = [
            {
                "_index": self.index_name,
                "_id": chunk["chunk_id"],
                "_source": chunk
            }
            for chunk in chunks
        ]
        
        success, _ = bulk(self.client, actions)
        return success == len(chunks)
    
    # 别名方法，保持兼容性
    def batch_index_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """批量索引文档切片（index_chunks的别名）"""
        return self.index_chunks(chunks)
    
    def search_chunks(
        self,
        query: str,
        knowledge_ids: List[int],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索文档切片（BM25算法）
        
        Args:
            query: 查询文本
            knowledge_ids: 知识库ID列表
            top_k: 返回结果数量
        
        Returns:
            匹配的切片列表，包含_score字段
        """
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["content^2", "metadata.heading"],
                                "type": "best_fields"
                            }
                        }
                    ],
                    "filter": [
                        {
                            "terms": {
                                "knowledge_id": knowledge_ids
                            }
                        }
                    ]
                }
            },
            "size": top_k,
            "_source": ["chunk_id", "document_id", "chunk_index", "content", "metadata"]
        }
        
        response = self.client.search(index=self.index_name, body=search_body)
        
        results = []
        for hit in response["hits"]["hits"]:
            result = hit["_source"]
            # 归一化BM25分数到0-1范围
            result["score"] = hit["_score"] / (hit["_score"] + 1)
            results.append(result)
        
        return results
    
    def delete_by_document(self, document_id: int) -> bool:
        """
        删除指定文档的所有切片
        
        Args:
            document_id: 文档ID
        
        Returns:
            是否成功
        """
        query = {
            "query": {
                "term": {
                    "document_id": document_id
                }
            }
        }
        
        response = self.client.delete_by_query(index=self.index_name, body=query)
        return response["deleted"] > 0
    
    def delete_by_knowledge(self, knowledge_id: int) -> bool:
        """
        删除指定知识库的所有切片
        
        Args:
            knowledge_id: 知识库ID
        
        Returns:
            是否成功
        """
        query = {
            "query": {
                "term": {
                    "knowledge_id": knowledge_id
                }
            }
        }
        
        response = self.client.delete_by_query(index=self.index_name, body=query)
        return response["deleted"] >= 0
    
    def get_chunk_count(self, knowledge_id: int) -> int:
        """
        获取知识库的切片数量
        
        Args:
            knowledge_id: 知识库ID
        
        Returns:
            切片数量
        """
        query = {
            "query": {
                "term": {
                    "knowledge_id": knowledge_id
                }
            }
        }
        
        response = self.client.count(index=self.index_name, body=query)
        return response["count"]
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        根据chunk_id获取切片内容
        
        Args:
            chunk_id: 切片ID
        
        Returns:
            切片数据，包含 content, filename 等字段，如不存在返回 None
        """
        try:
            response = self.client.get(index=self.index_name, id=chunk_id)
            if response["found"]:
                source = response["_source"]
                # 提取文件名，优先从 metadata.file_name 获取
                filename = source.get("metadata", {}).get("file_name", "unknown")
                if filename == "unknown":
                    filename = source.get("filename", "unknown")
                
                return {
                    "chunk_id": source.get("chunk_id", chunk_id),
                    "document_id": source.get("document_id"),
                    "knowledge_id": source.get("knowledge_id"),
                    "content": source.get("content", ""),
                    "filename": filename,
                    "metadata": source.get("metadata", {}),
                    "chunk_index": source.get("chunk_index")
                }
            return None
        except Exception as e:
            print(f"[错误] 获取chunk失败 (chunk_id={chunk_id}): {e}")
            return None
    
    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取多个chunk的内容
        
        Args:
            chunk_ids: 切片ID列表
        
        Returns:
            切片数据列表
        """
        if not chunk_ids:
            return []
        
        try:
            response = self.client.mget(
                index=self.index_name,
                body={"ids": chunk_ids}
            )
            
            results = []
            for doc in response["docs"]:
                if doc.get("found"):
                    source = doc["_source"]
                    filename = source.get("metadata", {}).get("file_name", "unknown")
                    if filename == "unknown":
                        filename = source.get("filename", "unknown")
                    
                    results.append({
                        "chunk_id": source.get("chunk_id", doc["_id"]),
                        "document_id": source.get("document_id"),
                        "knowledge_id": source.get("knowledge_id"),
                        "content": source.get("content", ""),
                        "filename": filename,
                        "metadata": source.get("metadata", {}),
                        "chunk_index": source.get("chunk_index")
                    })
            return results
        except Exception as e:
            print(f"[错误] 批量获取chunks失败: {e}")
            return []
    
    def close(self):
        """关闭连接"""
        self.client.close()


# 创建全局ES客户端实例
es_client = ESClient()
