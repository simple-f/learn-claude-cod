#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量数据库模块

使用 FAISS 作为向量数据库

融合课程：adv04 (知识管理)
"""

import pickle
from pathlib import Path
from typing import List, Dict, Any

import numpy as np

try:
    import faiss
except ImportError:
    print("⚠️  未安装 faiss，请运行：pip install faiss-cpu")
    faiss = None


class VectorDatabase:
    """FAISS 向量数据库"""
    
    def __init__(self, db_path: str):
        """
        初始化向量数据库
        
        参数:
            db_path: 数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # 向量维度（由 embedding 模型决定）
        self.dimension = 384  # all-MiniLM-L6-v2 的维度
        
        # 初始化 FAISS 索引
        self.index = None
        self.chunks = []
        
        # 加载现有数据库
        self._load()
    
    def _load(self):
        """加载数据库"""
        index_path = self.db_path / "index.faiss"
        chunks_path = self.db_path / "chunks.pkl"
        
        if index_path.exists() and chunks_path.exists():
            if faiss:
                self.index = faiss.read_index(str(index_path))
            with open(chunks_path, 'rb') as f:
                self.chunks = pickle.load(f)
            print(f"✅ 加载向量数据库：{len(self.chunks)} 个向量")
        else:
            print("🆕 创建新的向量数据库")
            if faiss:
                self.index = faiss.IndexFlatL2(self.dimension)
    
    def add(self, chunks: List[Dict], embeddings: np.ndarray):
        """
        添加向量
        
        参数:
            chunks: 文档片段
            embeddings: 向量数组
        """
        if faiss:
            # 添加到 FAISS 索引
            self.index.add(embeddings.astype('float32'))
        
        # 保存片段
        self.chunks.extend(chunks)
        
        # 保存到磁盘
        self._save()
    
    def search(self, query_embedding: np.ndarray, top_k: int = 3) -> List[Dict]:
        """
        检索向量
        
        参数:
            query_embedding: 查询向量
            top_k: 返回结果数
        
        返回:
            检索结果
        """
        if not self.index or self.index.ntotal == 0:
            return []
        
        # FAISS 检索
        distances, indices = self.index.search(
            query_embedding.reshape(1, -1).astype('float32'),
            top_k
        )
        
        # 提取结果
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                results.append({
                    **self.chunks[idx],
                    "score": float(distances[0][i])
                })
        
        return results
    
    def _save(self):
        """保存到磁盘"""
        if faiss and self.index:
            index_path = self.db_path / "index.faiss"
            faiss.write_index(self.index, str(index_path))
        
        chunks_path = self.db_path / "chunks.pkl"
        with open(chunks_path, 'wb') as f:
            pickle.dump(self.chunks, f)
    
    def clear(self):
        """清空数据库"""
        if faiss:
            self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []
        self._save()
        print("✅ 向量数据库已清空")
    
    def __len__(self) -> int:
        """返回向量数量"""
        return len(self.chunks)
