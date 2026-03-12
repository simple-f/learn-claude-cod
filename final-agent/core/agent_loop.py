#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Loop - 核心引擎

融合课程：s01 (Agent Loop) + s06 (Context Compact)
"""

import asyncio
import logging
from typing import List, Dict, Optional
from pathlib import Path

from .llm_client import LLMClient
from .state_manager import StateManager
from ..tools.registry import ToolRegistry
from ..memory.session import SessionManager
from ..memory.compressor import ContextCompressor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AgentLoop:
    """Agent 核心循环"""
    
    def __init__(self, config: Dict):
        """
        初始化 Agent
        
        参数:
            config: 配置字典
        """
        self.config = config
        self.llm = LLMClient(config)
        self.tools = ToolRegistry()
        self.memory = SessionManager(config)
        self.state = StateManager()
        self.compressor = ContextCompressor(config)
        
        logger.info(f"Agent 初始化完成，加载 {len(self.tools)} 个工具")
    
    async def run(self, user_input: str, session_id: str = "default") -> str:
        """
        运行 Agent 循环
        
        流程：
        1. 加载会话
        2. 添加用户输入
        3. 循环调用 LLM + 执行工具
        4. 上下文压缩（如需要）
        5. 保存会话
        
        参数:
            user_input: 用户输入
            session_id: 会话 ID
        
        返回:
            Agent 回答
        """
        logger.info(f"开始处理用户输入：{user_input[:50]}...")
        
        # 1. 加载会话
        messages = self.memory.get_session(session_id)
        messages.append({"role": "user", "content": user_input})
        
        # 2. 循环
        max_iterations = self.config.get("max_iterations", 30)
        
        for iteration in range(max_iterations):
            logger.debug(f"第 {iteration + 1} 轮循环")
            
            # 3. 调用 LLM
            response = await self.llm.chat(messages)
            messages.append({"role": "assistant", "content": response.content})
            
            # 4. 检查是否完成
            if response.stop_reason != "tool_use":
                logger.info(f"任务完成，迭代 {iteration + 1} 轮")
                return response.text
            
            # 5. 执行工具
            results = await self.tools.execute(response.tools)
            messages.append({"role": "user", "content": results})
            
            # 6. 上下文压缩（如需要）
            if self.memory.needs_compact(messages):
                logger.info("触发上下文压缩")
                messages = await self.compressor.auto_compact(messages)
        
        logger.warning(f"达到最大迭代次数 ({max_iterations})")
        return "抱歉，任务过于复杂，已达到最大迭代次数。"
    
    async def chat(self, user_id: str, message: str) -> str:
        """
        聊天接口（带会话管理）
        
        参数:
            user_id: 用户 ID
            message: 消息
        
        返回:
            回答
        """
        session_id = f"session_{user_id}"
        return await self.run(message, session_id)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "tools_loaded": len(self.tools),
            "active_sessions": len(self.memory.sessions),
            "state": self.state.get_current_state()
        }
