#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding 向量化模块

使用 Sentence Transformers 模型

融合课程：s05 (Skills 知识加载)
"""

from typing import List
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("⚠️  未安装 sentence-transformers，请运行：pip install sentence-transformers")
    SentenceTransformer = None


class TextEmbedder:
    """文本向量化器"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        初始化向量化器
        
        参数:
            model_name: 模型名称
        """
        self.model_name = model_name
        self.model = None
        
        # 懒加载模型
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        if SentenceTransformer:
            print(f"🤖 加载 Embedding 模型：{self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            print("✅ 模型加载成功")
        else:
            print("⚠️  使用模拟向量化（性能较差）")
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        向量化文本
        
        参数:
            texts: 文本列表
        
        返回:
            向量数组
        """
        if self.model:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
        else:
            # 模拟向量化（仅用于测试）
            embeddings = np.random.rand(len(texts), 384)
        
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """
        向量化单个文本
        
        参数:
            text: 文本
        
        返回:
            向量
        """
        embeddings = self.encode([text])
        return embeddings[0]
