"""
Elasticsearch客户端封装 (异步)
"""
import logging
from typing import List, Dict, Any, Optional
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from app.core.config import settings

logger = logging.getLogger(__name__)


class ESClient:
    """Elasticsearch客户端封装类 (异步)"""
    
    def __init__(self):
        self.client = AsyncElasticsearch([settings.ES_HOST])
        self.index_name = settings.ES_INDEX_NAME
    
    async def check_ik_analyzer(self) -> bool:
        """
        检查ES是否安装了IK分词器插件，以及分词器是否可用
        
        Returns:
            bool: 是否可用
        """
        try:
            # 1. 检查插件列表
            plugins = await self.client.cat.plugins(format="json")
            ik_installed = any("analysis-ik" in p.get("component", "") for p in plugins)
            
            if not ik_installed:
                logger.error("Elasticsearch 未安装 analysis-ik 插件")
                return False
            
            # 2. 测试分词器是否可用
            test_body = {
                "analyzer": "ik_max_word",
                "text": "测试分词器"
            }
            try:
                # 尝试对临时索引进行分析测试，或者直接测试全局分词器
                await self.client.indices.analyze(body=test_body)
                logger.info("Elasticsearch IK 分词器校验成功")
                return True
            except Exception as e:
                logger.error(f"Elasticsearch IK 分词器测试失败: {e}")
                return False
                
        except Exception as e:
            logger.error(f"校验 Elasticsearch 插件失败: {e}")
            return False

    async def ensure_index(self):
        """确保索引存在，如不存在则创建"""
        if not await self.client.indices.exists(index=self.index_name):
            await self._create_index()
    
    async def _create_index(self, use_standard_fallback: bool = False):
        """创建文档切片索引"""
        analyzer = "ik_max_word_analyzer" if not use_standard_fallback else "standard"
        search_analyzer = "ik_smart_analyzer" if not use_standard_fallback else "standard"
        
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
                        "analyzer": analyzer,
                        "search_analyzer": search_analyzer
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "file_name": {"type": "keyword"},
                            "page_number": {"type": "integer"},
                            "heading": {
                                "type": "text",
                                "analyzer": search_analyzer
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
        
        try:
            await self.client.indices.create(index=self.index_name, body=mapping)
            logger.info(f"创建ES索引: {self.index_name} (Analyzer: {analyzer})")
        except Exception as e:
            if "illegal_argument_exception" in str(e) and not use_standard_fallback:
                logger.warning(f"使用 IK 分词器创建索引失败，尝试使用 standard 分词器降级: {str(e)}")
                # 递归调用降级逻辑
                await self._create_index(use_standard_fallback=True)
            else:
                logger.error(f"创建ES索引最终失败: {str(e)}")
                raise e
    
    async def index_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        批量索引文档切片
        
        Args:
            chunks: 切片数据列表，每个切片包含chunk_id, content等字段
        
        Returns:
            是否成功
        """
        await self.ensure_index()
        actions = [
            {
                "_index": self.index_name,
                "_id": chunk["chunk_id"],
                "_source": chunk
            }
            for chunk in chunks
        ]
        
        try:
            success, errors = await async_bulk(self.client, actions, raise_on_error=False)
            if errors:
                logger.error(f"ES 批量索引部分失败: {errors}")
                # 记录详细的失败请求上下文
                for error_item in errors:
                    item = error_item.get("index", error_item.get("create", {}))
                    if "illegal_argument_exception" in str(item.get("error", "")):
                        logger.warning("检测到分词器配置异常，可能需要触发降级处理")
            return success == len(chunks)
        except Exception as e:
            logger.error(f"ES 批量索引发生异常: {str(e)}")
            # 捕获详细响应
            if hasattr(e, 'info'):
                logger.error(f"ES 错误详细信息: {e.info}")
            return False
    
    async def batch_index_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """批量索引文档切片（index_chunks的别名）"""
        return await self.index_chunks(chunks)
    
    async def search_chunks(
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
        await self.ensure_index()
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
        
        response = await self.client.search(index=self.index_name, body=search_body)
        
        results = []
        for hit in response["hits"]["hits"]:
            result = hit["_source"]
            # 归一化BM25分数到0-1范围
            result["score"] = hit["_score"] / (hit["_score"] + 1)
            results.append(result)
        
        return results
    
    async def delete_by_document(self, document_id: int) -> bool:
        """
        删除指定文档的所有切片
        
        Args:
            document_id: 文档ID
        
        Returns:
            是否成功
        """
        await self.ensure_index()
        query = {
            "query": {
                "term": {
                    "document_id": document_id
                }
            }
        }
        
        response = await self.client.delete_by_query(index=self.index_name, body=query)
        return response["deleted"] > 0
    
    async def delete_by_knowledge(self, knowledge_id: int) -> bool:
        """
        删除指定知识库的所有切片
        
        Args:
            knowledge_id: 知识库ID
        
        Returns:
            是否成功
        """
        await self.ensure_index()
        query = {
            "query": {
                "term": {
                    "knowledge_id": knowledge_id
                }
            }
        }
        
        response = await self.client.delete_by_query(index=self.index_name, body=query)
        return response["deleted"] >= 0
    
    async def get_chunk_count(self, knowledge_id: int) -> int:
        """
        获取知识库的切片数量
        
        Args:
            knowledge_id: 知识库ID
        
        Returns:
            切片数量
        """
        await self.ensure_index()
        query = {
            "query": {
                "term": {
                    "knowledge_id": knowledge_id
                }
            }
        }
        
        response = await self.client.count(index=self.index_name, body=query)
        return response["count"]
    
    async def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        根据chunk_id获取切片内容
        
        Args:
            chunk_id: 切片ID
        
        Returns:
            切片数据，包含 content, filename 等字段，如不存在返回 None
        """
        try:
            await self.ensure_index()
            response = await self.client.get(index=self.index_name, id=chunk_id)
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
            logger.error(f"获取chunk失败 (chunk_id={chunk_id}): {e}")
            return None
    
    async def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
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
            await self.ensure_index()
            response = await self.client.mget(
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
            logger.error(f"批量获取chunks失败: {e}")
            return []
    
    async def close(self):
        """关闭连接"""
        await self.client.close()


# 创建全局ES客户端实例
es_client = ESClient()
