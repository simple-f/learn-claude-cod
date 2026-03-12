#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 模块测试

测试内容：
- 文档加载
- 文档切片
- 向量检索
- 检索延迟
"""

import pytest
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.retriever import RAGRetriever
from src.config import Config


@pytest.fixture
def config():
    """配置对象"""
    return Config.load()


@pytest.fixture
def retriever(config):
    """RAG 检索器"""
    r = RAGRetriever(config)
    r.load_documents("data/knowledge")
    return r


class TestRAGRetriever:
    """RAG 检索器测试"""
    
    def test_load_documents(self, retriever):
        """测试文档加载"""
        assert len(retriever.documents) > 0, "文档加载失败"
        print(f"✅ 加载了 {len(retriever.documents)} 个文档")
    
    @pytest.mark.asyncio
    async def test_retrieve(self, retriever):
        """测试检索功能"""
        results = await retriever.retrieve("怎么退货？", top_k=3)
        
        assert len(results) > 0, "检索结果为空"
        assert isinstance(results, list), "检索结果应为列表"
        print(f"✅ 检索到 {len(results)} 条结果")
    
    @pytest.mark.asyncio
    async def test_retrieve_content(self, retriever):
        """测试检索内容质量"""
        results = await retriever.retrieve("怎么退货？", top_k=3)
        
        # 检查是否包含相关关键词
        content = " ".join(results)
        assert "退货" in content or "订单" in content, "检索内容不相关"
        print(f"✅ 检索内容相关：{content[:100]}...")
    
    @pytest.mark.asyncio
    async def test_retrieve_latency(self, retriever):
        """测试检索延迟"""
        import time
        
        start = time.time()
        await retriever.retrieve("怎么退货？", top_k=3)
        duration = time.time() - start
        
        assert duration < 0.1, f"检索延迟过高：{duration:.3f}秒"
        print(f"✅ 检索延迟：{duration*1000:.1f}ms")
    
    @pytest.mark.asyncio
    async def test_multiple_queries(self, retriever):
        """测试多次查询"""
        queries = [
            "怎么退货？",
            "退款多久到账？",
            "多久能发货？"
        ]
        
        for query in queries:
            results = await retriever.retrieve(query, top_k=3)
            assert len(results) > 0, f"查询 '{query}' 结果为空"
        
        print(f"✅ 完成 {len(queries)} 次查询")
    
    def test_document_splitting(self, retriever):
        """测试文档切片"""
        content = "段落 1。\n\n段落 2。\n\n段落 3。\n\n段落 4。"
        chunks = retriever._split_document(content, chunk_size=20)
        
        assert len(chunks) > 1, "文档切片失败"
        assert all(len(c) > 0 for c in chunks), "存在空切片"
        print(f"✅ 文档切片：{len(chunks)} 个片段")
    
    def test_clear(self, retriever):
        """测试清空知识库"""
        retriever.clear()
        assert len(retriever.documents) == 0, "文档未清空"
        print("✅ 知识库已清空")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
