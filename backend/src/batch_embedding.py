#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import List, Union
import numpy as np
from scipy.spatial.distance import cosine
from transformers import AutoTokenizer, AutoModel
import torch

# ==================== 原有模型类保持不变 ====================

current_dir = Path(__file__).resolve().parent
# 注意：这里保持了你原来的路径写法
model_path = (current_dir.parent / "models" / "Qwen" / "Qwen3-Embedding-0___6B").resolve()
print(f"解析后的模型绝对路径: {model_path}")


class QwenEmbeddingModel:
    """Qwen3-Embedding 模型封装类"""
    
    def __init__(self, model_path: Union[str, Path], device: str = "auto"):
        self.model_path = Path(model_path)
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"模型目录不存在: {self.model_path}")

        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"正在加载模型: {self.model_path}")
        print(f"使用设备: {self.device}")
        
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
        print("✓ 模型加载完成")
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        normalize: bool = True,
        max_length: int = 512
    ) -> np.ndarray:
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

# ==================== 新增：批量向量化封装类 ====================

class BatchTextEncoder:
    """
    纯文本批量向量化封装器
    
    功能：将一个大的文本列表拆分为小批次进行处理，防止显存溢出
    """
    
    def __init__(self, model_path: Union[str, Path], device: str = "auto"):
        """
        初始化编码器，内部加载 QwenEmbeddingModel
        
        Args:
            model_path: 模型路径
            device: 设备 ('cpu', 'cuda', 'auto')
        """
        print(f"初始化 BatchTextEncoder...")
        self.model = QwenEmbeddingModel(model_path, device=device)
        self.embedding_dim = None # 首次运行后自动获取维度
        
    def transform(
        self, 
        texts: List[str], 
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        批量将文本转化为向量
        
        Args:
            texts: 待编码的文本列表 (例如: ["句子1", "句子2", ...])
            batch_size: 每次送入模型的文本数量。如果显存不足，请调小此值 (如 16 或 8)
            show_progress: 是否在控制台显示进度条
            
        Returns:
            numpy.ndarray: 形状为 的向量矩阵
        """
        if not texts:
            return np.array([])
            
        total_texts = len(texts)
        all_embeddings = []
        
        # 尝试导入 tqdm，如果没有安装则使用简单的打印
        try:
            from tqdm import tqdm
            range_iter = tqdm(range(0, total_texts, batch_size), desc="Encoding")
        except ImportError:
            range_iter = range(0, total_texts, batch_size)
            
        # 分批处理循环
        for start_idx in range_iter:
            end_idx = min(start_idx + batch_size, total_texts)
            batch_texts = texts[start_idx:end_idx]
            
            # 调用底层模型进行编码
            batch_emb = self.model.encode(batch_texts, normalize=True)
            
            all_embeddings.append(batch_emb)
            
            # 记录维度
            if self.embedding_dim is None:
                self.embedding_dim = batch_emb.shape[1]
                
            # 简单的进度反馈 (如果没有 tqdm)
            if show_progress and 'tqdm' not in sys.modules:
                print(f"Processed: {end_idx}/{total_texts}", end='\r')

        # 垂直堆叠所有批次结果
        final_embeddings = np.vstack(all_embeddings)
        
        if show_progress and 'tqdm' not in sys.modules:
            print() # 换行
            
        return final_embeddings

# ==================== 测试与辅助函数 ====================

def test_batch_encoder_wrapper():
    """测试批量编码封装器"""
    print("\n" + "="*60)
    print("测试 BatchTextEncoder (纯文本批量转化)")
    print("="*60)
    
    # 1. 初始化封装器
    encoder = BatchTextEncoder(model_path, device="cuda")
    
    # 2. 准备模拟数据 (模拟大量纯文本)
    print(f"\n准备测试数据...")
    raw_texts = [
        "人工智能是计算机科学的一个分支",
        "Python是一门编程语言",
        "机器学习是AI的子领域",
        "深度学习使用神经网络模拟人脑",
        "自然语言处理处理文本和语音",
        "计算机视觉让机器看懂图片",
        "强化学习通过试错来学习策略",
        "生成式AI能够创造新的内容",
        "大语言模型如GPT具备强大的理解力",
        "Transformer架构改变了NLP领域"
    ]
    
    # 将数据复制N份以模拟大数据量测试 (例如100条)
    texts = raw_texts * 10 
    print(f"总文本数量: {len(texts)}")
    
    # 3. 调用封装方法进行转化
    # 设置 batch_size=4 仅为了演示分批过程，实际使用可以设为 32, 64 等
    embeddings = encoder.transform(texts, batch_size=4, show_progress=True)
    
    # 4. 查看结果
    print(f"\n转化完成！")
    print(f"输出向量形状: {embeddings.shape}")
    print(f"向量维度: {embeddings.shape[1]}")
    print(f"向量范数 (前3条):")
    for i in range(3):
        norm = np.linalg.norm(embeddings[i])
        print(f"  Text {i}: {norm:.6f}")


# 保留原有的其他测试函数以便兼容...
def test_basic_embedding(model: QwenEmbeddingModel):
    print("\n测试原模型单条/小批量编码...")
    texts = ["测试文本1", "测试文本2"]
    embs = model.encode(texts)
    print(f"形状: {embs.shape}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qwen3-Embedding 批量向量化工具")
    parser.add_argument("--device", type=str, default="auto", choices=["cpu", "cuda", "auto"])
    parser.add_argument("--test", type=str, default="batch", 
                       choices=["batch", "old"], help="运行新批量测试或旧测试")
    
    args = parser.parse_args(argv)
    
    try:
        if args.test == "batch":
            # 运行新的批量封装测试
            test_batch_encoder_wrapper()
        else:
            # 运行旧的模型加载测试
            model = QwenEmbeddingModel(model_path, args.device)
            test_basic_embedding(model)
            
        return 0
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
