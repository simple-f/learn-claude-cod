#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 检索器模块

融合课程：adv04 (知识管理) + s05 (Skills)

功能：
1. 文档加载
2. 文档切片
3. 向量化
4. 检索
"""

import asyncio
from typing import List, Dict
from pathlib import Path

from .vector_db import VectorDatabase
from .embedder import TextEmbedder


class RAGRetriever:
    """RAG 检索器"""
    
    def __init__(self, config):
        """
        初始化检索器
        
        参数:
            config: 配置对象
        """
        self.config = config
        self.embedder = TextEmbedder(config.embedding_model)
        
        # 动态获取向量维度
        try:
            # 尝试获取模型的维度
            test_embedding = self.embedder.encode(["test"])[0]
            dimension = len(test_embedding)
        except:
            dimension = 384  # 默认维度
        
        self.vector_db = VectorDatabase(config.vector_db_path, dimension)
        self.documents = []
    
    def load_documents(self, knowledge_path: str):
        """
        加载知识库文档
        
        参数:
            knowledge_path: 知识库路径
        """
        knowledge_dir = Path(knowledge_path)
        
        if not knowledge_dir.exists():
            print(f"⚠️  知识库不存在：{knowledge_path}")
            return
        
        # 加载所有文本文件
        for file_path in knowledge_dir.glob("*.txt"):
            print(f"📄 加载文档：{file_path.name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.documents.append({
                    "source": str(file_path),
                    "content": content
                })
        
        # 文档切片和向量化
        self._process_documents()
    
    def _process_documents(self):
        """处理文档：切片 + 向量化"""
        if not self.documents:
            print("⚠️  没有文档需要处理")
            return
        
        print(f"📝 处理 {len(self.documents)} 个文档...")
        
        # 1. 文档切片
        chunks = []
        for doc in self.documents:
            doc_chunks = self._split_document(doc["content"])
            for chunk in doc_chunks:
                chunks.append({
                    "source": doc["source"],
                    "content": chunk
                })
        
        print(f"✂️  切片完成：{len(chunks)} 个片段")
        
        # 2. 向量化
        print("🔢 计算向量...")
        contents = [chunk["content"] for chunk in chunks]
        embeddings = self.embedder.encode(contents)
        
        # 3. 存储到向量数据库
        print("💾 存储到向量数据库...")
        self.vector_db.add(chunks, embeddings)
        
        print(f"✅ 处理完成，共 {len(chunks)} 个向量")
    
    def _split_document(self, content: str, chunk_size: int = 500) -> List[str]:
        """
        文档切片
        
        参数:
            content: 文档内容
            chunk_size: 每片大小（字符数）
        
        返回:
            切片列表
        """
        chunks = []
        
        # 简单按段落切片
        paragraphs = content.split("\n\n")
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) < chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        检索相关知识
        
        参数:
            query: 查询问题
            top_k: 返回结果数
        
        返回:
            相关知识列表
        """
        # 1. 向量化查询
        query_embedding = self.embedder.encode([query])[0]
        
        # 2. 检索
        results = self.vector_db.search(query_embedding, top_k)
        
        # 3. 提取内容
        knowledge = [result["content"] for result in results]
        
        return knowledge
    
    def clear(self):
        """清空知识库"""
        self.documents = []
        self.vector_db.clear()
