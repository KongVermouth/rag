"""
重排序模块
"""
import logging
from typing import List, Tuple
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

class Reranker:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Reranker, cls).__new__(cls)
            cls._instance.model = None
        return cls._instance

    def load_model(self, model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"):
        """加载重排序模型"""
        if not self.model:
            try:
                logger.info(f"正在加载重排序模型: {model_name} ...")
                self.model = CrossEncoder(model_name)
                logger.info("重排序模型加载成功")
            except Exception as e:
                logger.error(f"加载重排序模型失败: {e}")
                self.model = None

    def rerank(self, query: str, documents: List[str], top_k: int) -> List[Tuple[int, float]]:
        """
        对文档进行重排序
        
        Args:
            query: 查询语句
            documents: 文档内容列表
            top_k: 返回前K个
            
        Returns:
            List[Tuple[int, float]]: (原始索引, 分数) 列表
        """
        if not self.model:
            self.load_model()
        
        if not self.model or not documents:
            return [(i, 0.0) for i in range(min(len(documents), top_k))]
            
        pairs = [[query, doc] for doc in documents]
        
        try:
            scores = self.model.predict(pairs)
            
            # 将分数与原始索引组合
            scored_docs = list(enumerate(scores))
            
            # 按分数降序排序
            sorted_docs = sorted(scored_docs, key=lambda x: x[1], reverse=True)
            
            return sorted_docs[:top_k]
        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return [(i, 0.0) for i in range(min(len(documents), top_k))]

# 全局重排序实例
reranker = Reranker()
