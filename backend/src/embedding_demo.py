#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import List, Union
import numpy as np
from scipy.spatial.distance import cosine
from transformers import AutoTokenizer, AutoModel
import torch


current_dir = Path(__file__).resolve().parent
model_path = (current_dir.parent / "models" / "Qwen" / "Qwen3-Embedding-0___6B").resolve()
print(f"解析后的模型绝对路径: {model_path}")


class QwenEmbeddingModel:
    """Qwen3-Embedding 模型封装类"""
    
    def __init__(self, model_path: Union[str, Path], device: str = "auto"):
        """
        初始化模型
        
        Args:
            model_path: 本地模型路径
            device: 运行设备 ('cpu', 'cuda', 'auto')
        """
        self.model_path = Path(model_path)
        
        # 再次确保路径对象存在
        if not self.model_path.exists():
            raise FileNotFoundError(f"模型目录不存在: {self.model_path}")

        # 自动选择设备
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"正在加载模型: {self.model_path}")
        print(f"使用设备: {self.device}")
        
        # 加载 tokenizer 和 model
        # --- 修改开始 ---
        # 关键修改：添加 local_files_only=True
        # 这会强制 Transformers 只从本地加载，忽略 HF Hub 的 ID 验证逻辑
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
        # --- 修改结束 ---
        
        # 设置为评估模式
        self.model.eval()
        print("✓ 模型加载完成")
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        normalize: bool = True,
        max_length: int = 512
    ) -> np.ndarray:
        """
        将文本编码为向量
        
        Args:
            texts: 单个文本或文本列表
            normalize: 是否对向量进行L2归一化
            max_length: 最大序列长度
            
        Returns:
            文本嵌入向量，shape: (n_texts, embedding_dim)
        """
        if isinstance(texts, str):
            texts = [texts]
        
        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        ).to(self.device)
        
        # 推理
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Qwen embedding 通常取最后一层隐藏状态的 [CLS] token 或平均池化
            embeddings = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        
        # 转为 numpy
        embeddings = embeddings.cpu().numpy()
        
        # L2 归一化
        if normalize:
            embeddings = embeddings / np.linalg.norm(
                embeddings, axis=1, keepdims=True
            )
        
        return embeddings
    
    def compute_similarity(
        self, 
        text1: Union[str, List[str]], 
        text2: Union[str, List[str]]
    ) -> np.ndarray:
        """
        计算文本间的余弦相似度
        
        Args:
            text1: 第一组文本
            text2: 第二组文本
            
        Returns:
            相似度矩阵
        """
        emb1 = self.encode(text1, normalize=True)
        emb2 = self.encode(text2, normalize=True)
        
        # 余弦相似度 = 1 - 余弦距离
        similarities = []
        for e1 in emb1:
            row = []
            for e2 in emb2:
                sim = 1 - cosine(e1, e2)
                row.append(sim)
            similarities.append(row)
        
        return np.array(similarities)


def print_separator(char: str = "=", length: int = 60):
    """打印分隔线"""
    print(char * length)


def test_basic_embedding(model: QwenEmbeddingModel):
    """测试1: 基本文本嵌入"""
    print("\n" + "="*60)
    print("测试 1: 基本文本嵌入")
    print("="*60)
    
    texts = [
        "人工智能是计算机科学的一个分支",
        "Python是一门编程语言",
        "机器学习是AI的子领域"
    ]
    
    embeddings = model.encode(texts)
    
    print(f"\n输入文本数: {len(texts)}")
    print(f"嵌入维度: {embeddings.shape[1]}")
    print(f"嵌入向量形状: {embeddings.shape}")
    
    print("\n各文本嵌入向量前5个维度的值:")
    for i, (text, emb) in enumerate(zip(texts, embeddings), 1):
        print(f"\n{i}. {text}")
        print(f"   前5维: {emb[:5]}")
        print(f"   范数: {np.linalg.norm(emb):.6f}")


def test_similarity(model: QwenEmbeddingModel):
    """测试2: 文本相似度计算"""
    print("\n" + "="*60)
    print("测试 2: 文本相似度计算")
    print("="*60)
    
    query = "如何学习机器学习"
    candidates = [
        "机器学习是AI的一个重要分支",
        "今天天气真好",
        "深度学习入门教程",
        "我喜欢吃苹果",
        "Python机器学习实战指南"
    ]
    
    print(f"\n查询文本: 「{query}」")
    print("\n候选文本:")
    for i, text in enumerate(candidates, 1):
        print(f"  {i}. {text}")
    
    similarities = model.compute_similarity(query, candidates)
    
    print("\n相似度得分:")
    sorted_indices = np.argsort(similarities[0])[::-1]  # 降序
    
    for rank, idx in enumerate(sorted_indices, 1):
        sim = similarities[0][idx]
        print(f"  {rank}. [{sim:.4f}] {candidates[idx]}")


def test_batch_encoding(model: QwenEmbeddingModel):
    """测试3: 批量编码效率"""
    print("\n" + "="*60)
    print("测试 3: 批量编码效率对比")
    print("="*60)
    
    import time
    
    test_texts = [
        "自然语言处理是人工智能的重要领域",
        "计算机视觉让机器能够识别图像",
        "强化学习通过奖励机制训练智能体",
        "生成式AI可以创作新的内容",
        "大语言模型展示了强大的理解能力"
    ]
    
    # 单条处理
    start_time = time.time()
    single_results = [model.encode(text) for text in test_texts]
    single_time = time.time() - start_time
    
    # 批量处理
    start_time = time.time()
    batch_results = model.encode(test_texts)
    batch_time = time.time() - start_time
    
    print(f"\n文本数量: {len(test_texts)}")
    print(f"单条处理耗时: {single_time:.3f}s")
    print(f"批量处理耗时: {batch_time:.3f}s")
    print(f"批量加速比: {single_time / batch_time:.2f}x")
    
    # 验证结果一致
    single_concat = np.vstack(single_results)
    max_diff = np.max(np.abs(single_concat - batch_results))
    print(f"单条与批量结果最大差异: {max_diff:.10f}")


def test_semantic_search(model: QwenEmbeddingModel):
    """测试4: 语义搜索演示"""
    print("\n" + "="*60)
    print("测试 4: 语义搜索演示")
    print("="*60)
    
    # 构建文档库
    documents = [
        {"id": 1, "content": "Transformer是处理序列数据的神经网络架构", "category": "深度学习"},
        {"id": 2, "content": "卷积神经网络CNN主要用于图像处理任务", "category": "计算机视觉"},
        {"id": 3, "content": "循环神经网络RNN适合处理时序数据", "category": "深度学习"},
        {"id": 4, "content": "BERT是双向编码的预训练语言模型", "category": "NLP"},
        {"id": 5, "content": "ResNet解决了深层网络的梯度消失问题", "category": "计算机视觉"},
        {"id": 6, "content": "Attention机制让模型能关注重要信息", "category": "深度学习"},
        {"id": 7, "content": "GPT系列是生成式预训练语言模型", "category": "NLP"},
        {"id": 8, "content": "YOLO是一种实时的目标检测算法", "category": "计算机视觉"},
    ]
    
    # 预编码文档
    doc_texts = [doc["content"] for doc in documents]
    doc_embeddings = model.encode(doc_texts)
    
    # 查询
    queries = [
        "什么是注意力机制",
        "图像识别用什么模型",
        "文本生成有哪些模型"
    ]
    
    for query in queries:
        print(f"\n🔍 查询: 「{query}」")
        query_emb = model.encode(query)
        
        # 计算相似度
        similarities = np.dot(doc_embeddings, query_emb.T).flatten()
        
        # 显示Top-3
        top_k = 3
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        print(f"\nTop-{top_k} 匹配结果:")
        for rank, idx in enumerate(top_indices, 1):
            doc = documents[idx]
            sim = similarities[idx]
            print(f"  {rank}. [{sim:.4f}] ({doc['category']}) {doc['content']}")


def interactive_mode(model: QwenEmbeddingModel):
    """交互式模式"""
    print("\n" + "="*60)
    print("交互式模式")
    print("="*60)
    print("输入 'quit' 或 'exit' 退出\n")
    
    while True:
        try:
            text = input("请输入文本: ").strip()
            
            if text.lower() in ('quit', 'exit', 'q'):
                print("再见！")
                break
            
            if not text:
                continue
            
            embedding = model.encode(text)
            print(f"\n嵌入向量形状: {embedding.shape}")
            print(f"前10个维度的值:\n{embedding[0][:10]}")
            print(f"向量范数: {np.linalg.norm(embedding[0]):.6f}\n")
            
        except KeyboardInterrupt:
            print("\n\n再见！")
            break


def main(argv: list[str] | None = None) -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Qwen3-Embedding 模型加载与测试"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["cpu", "cuda", "auto"],
        help="运行设备"
    )
    parser.add_argument(
        "--test",
        type=str,
        default="all",
        choices=["basic", "similarity", "batch", "search", "all", "none"],
        help="指定运行的测试"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="启用交互式模式"
    )
    
    args = parser.parse_args(argv)
    
    try:
        # 加载模型，直接使用全局变量 model_path (已经是 Path 对象)
        model = QwenEmbeddingModel(model_path, args.device)
        
        # 运行测试
        if args.test in ("basic", "all"):
            test_basic_embedding(model)
        
        if args.test in ("similarity", "all"):
            test_similarity(model)
        
        if args.test in ("batch", "all"):
            test_batch_encoding(model)
        
        if args.test in ("search", "all"):
            test_semantic_search(model)
        
        # 交互式模式
        if args.interactive:
            interactive_mode(model)
        
        return 0
        
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
