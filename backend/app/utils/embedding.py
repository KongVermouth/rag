"""
Embedding向量化工具 - 基于 src/batch_embedding.py
"""
import logging
import yaml
import asyncio
import time
from pathlib import Path
from typing import List, Union, Dict, Any, Optional
import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch
import httpx
from app.core.config import settings
from app.core.exceptions import VectorizationFailedException

logger = logging.getLogger(__name__)

def load_siliconflow_config():
    """加载 SiliconFlow 配置文件"""
    config_path = Path("config/siliconflow.yml")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f).get("embedding", {})
        except Exception as e:
            logger.error(f"加载 siliconflow.yml 失败: {e}")
    return {}

# 加载配置
SF_CONFIG = load_siliconflow_config()


class EmbeddingModel:
    """Qwen3-Embedding 模型封装类"""

    def __init__(self, model_path: Union[str, Path] = None, device: str = "auto"):
        self.model_path = Path(model_path) if model_path else Path(settings.EMBEDDING_MODEL_PATH)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Embedding模型目录不存在: {self.model_path}")

        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"正在加载Embedding模型: {self.model_path}")
        logger.info(f"使用设备: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            trust_remote_code=True,
            local_files_only=True
        )
        self.model = AutoModel.from_pretrained(
            str(self.model_path),
            trust_remote_code=True,
            local_files_only=True
        ).to(self.device)

        self.model.eval()
        logger.info("[OK] Embedding模型加载完成")

    def encode(
        self,
        texts: Union[str, List[str]],
        normalize: bool = True,
        max_length: int = 512
    ) -> np.ndarray:
        """对文本进行向量化编码"""
        if isinstance(texts, str):
            texts = [texts]

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :]

        embeddings = embeddings.cpu().numpy()

        if normalize:
            embeddings = embeddings / np.linalg.norm(
                embeddings, axis=1, keepdims=True
            )

        return embeddings

    def batch_encode(
        self,
        texts: List[str],
        batch_size: int = None,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        批量将文本转化为向量
        
        Args:
            texts: 待编码的文本列表
            batch_size: 每批次处理的文本数量
            show_progress: 是否显示进度
            
        Returns:
            numpy.ndarray: 向量矩阵，形状为 (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])

        if batch_size is None:
            batch_size = settings.EMBEDDING_BATCH_SIZE

        total_texts = len(texts)
        all_embeddings = []

        # 尝试导入 tqdm
        if show_progress:
            try:
                from tqdm import tqdm
                range_iter = tqdm(range(0, total_texts, batch_size), desc="Encoding")
            except ImportError:
                range_iter = range(0, total_texts, batch_size)
        else:
            range_iter = range(0, total_texts, batch_size)

        # 分批处理
        for start_idx in range_iter:
            end_idx = min(start_idx + batch_size, total_texts)
            batch_texts = texts[start_idx:end_idx]

            batch_emb = self.encode(batch_texts, normalize=True)
            all_embeddings.append(batch_emb)

        # 合并所有批次结果
        final_embeddings = np.vstack(all_embeddings)
        return final_embeddings

    def get_embedding_dim(self) -> int:
        """获取向量维度"""
        test_emb = self.encode("test")
        return test_emb.shape[1]


# 全局Embedding模型实例（延迟初始化）
_embedding_model: EmbeddingModel = None


def get_embedding_model() -> EmbeddingModel:
    """获取全局Embedding模型实例（单例模式）"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model
