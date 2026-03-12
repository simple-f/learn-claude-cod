#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式输出模块

融合课程：adv06 (MCP 回传) + s08 (后台任务)

功能：
1. SSE 流式输出
2. 打字机效果
3. 异步流
"""

import asyncio
from typing import AsyncGenerator


class StreamingOutput:
    """流式输出器"""
    
    def __init__(self, config):
        """
        初始化流式输出器
        
        参数:
            config: 配置对象
        """
        self.config = config
        self.delay = config.stream_delay / 1000.0  # 转换为秒
    
    async def stream(self, text: str) -> AsyncGenerator[str, None]:
        """
        流式输出文本
        
        参数:
            text: 要输出的文本
        
        Yield:
            文本片段
        """
        # 按字分割（中文）
        for char in text:
            yield char
            await asyncio.sleep(self.delay)
    
    async def stream_words(self, text: str) -> AsyncGenerator[str, None]:
        """
        按词流式输出
        
        参数:
            text: 要输出的文本
        
        Yield:
            词语
        """
        # 按空格分割（英文）
        words = text.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word
            await asyncio.sleep(self.delay * 3)  # 词语延迟更长
    
    async def stream_lines(self, text: str) -> AsyncGenerator[str, None]:
        """
        按行流式输出
        
        参数:
            text: 要输出的文本
        
        Yield:
            行
        """
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                yield '\n'
            yield line
            await asyncio.sleep(self.delay * 5)  # 行延迟更长
