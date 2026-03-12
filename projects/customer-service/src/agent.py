#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能客服 Agent 核心模块

融合课程：
- adv02 (Session 管理)
- adv04 (RAG 知识检索)
- adv06 (流式输出)
"""

import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path

from .config import Config
from .rag.retriever import RAGRetriever
from .session.manager import SessionManager
from .intent.rule_matcher import RuleMatcher
from .stream.output import StreamingOutput

# 配置日志
logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI 库未安装，将使用模拟响应")


class CustomerServiceAgent:
    """智能客服 Agent"""
    
    def __init__(self, config: Config):
        """
        初始化客服 Agent
        
        参数:
            config: 配置对象
        """
        self.config = config
        self.rag = RAGRetriever(config)
        self.session_manager = SessionManager(config)
        self.intent_matcher = RuleMatcher()
        self.output = StreamingOutput(config)
        
        # 初始化 OpenAI 客户端
        if OPENAI_AVAILABLE and config.openai_api_key:
            self.client = AsyncOpenAI(api_key=config.openai_api_key)
        else:
            self.client = None
        
        # 统计信息
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0
        }
    
    def load_knowledge(self, knowledge_path: str):
        """
        加载知识库
        
        参数:
            knowledge_path: 知识库路径
        """
        self.rag.load_documents(knowledge_path)
    
    async def chat(self, user_id: str, message: str) -> str:
        """
        处理用户对话
        
        流程：
        1. 加载会话历史
        2. 意图识别
        3. 知识检索 (RAG)
        4. 答案生成
        5. 流式输出
        6. 保存会话
        
        参数:
            user_id: 用户 ID
            message: 用户消息
        
        返回:
            助手回答
        """
        # 统计
        self.stats["total_queries"] += 1
        
        try:
            # 1. 加载会话
            session = self.session_manager.get_session(user_id)
            history = session.get_history(last_n=5)
            
            # 2. 意图识别
            intent = self.intent_matcher.match(message)
            print(f"[意图：{intent}] ", end="", flush=True)
            
            # 3. 知识检索
            knowledge = []
            if intent in ["faq", "shipping", "return", "refund"]:
                knowledge = await self.rag.retrieve(message, top_k=3)
                if knowledge:
                    print(f"[检索到{len(knowledge)}条知识] ", end="", flush=True)
            
            # 4. 构建提示词
            prompt = self._build_prompt(message, history, knowledge, intent)
            
            # 5. 调用 LLM
            answer = await self._generate_answer(prompt)
            
            # 6. 流式输出
            async for chunk in self.output.stream(answer):
                print(chunk, end="", flush=True)
            
            # 7. 保存会话
            session.add_message("user", message)
            session.add_message("assistant", answer)
            
            # 统计
            self.stats["successful_queries"] += 1
            
            return answer
            
        except Exception as e:
            self.stats["failed_queries"] += 1
            raise e
    
    def _build_prompt(
        self,
        message: str,
        history: List[Dict],
        knowledge: List[str],
        intent: str
    ) -> str:
        """
        构建提示词
        
        参数:
            message: 用户消息
            history: 对话历史
            knowledge: 相关知识
            intent: 意图
        
        返回:
            提示词
        """
        # 系统提示
        system_prompt = """你是一个专业的电商客服助手。
请用专业、友好、简洁的语气回答用户问题。
如果不知道答案，请诚实告知，不要编造信息。"""
        
        # 对话历史
        history_text = ""
        if history:
            history_text = "\n对话历史：\n"
            for msg in history:
                role = "用户" if msg["role"] == "user" else "客服"
                history_text += f"{role}: {msg['content']}\n"
        
        # 相关知识
        knowledge_text = ""
        if knowledge:
            knowledge_text = "\n相关知识：\n"
            for i, k in enumerate(knowledge, 1):
                knowledge_text += f"{i}. {k}\n"
        
        # 完整提示
        prompt = f"""{system_prompt}
{history_text}
{knowledge_text}
用户问题：{message}

客服："""
        
        return prompt
    
    async def _generate_answer(self, prompt: str) -> str:
        """
        调用 LLM 生成答案
        
        参数:
            prompt: 提示词
        
        返回:
            AI 生成的答案
        """
        try:
            if self.client:
                # 调用 OpenAI API
                logger.info("调用 OpenAI API...")
                response = await self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "你是一个专业的电商客服助手。请用专业、友好、简洁的语气回答用户问题。如果不知道答案，请诚实告知，不要编造信息。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )
                answer = response.choices[0].message.content
                logger.info(f"OpenAI API 响应：{len(answer)} 字符")
            else:
                # 模拟响应（用于测试）
                logger.warning("使用模拟响应（未配置 OpenAI API）")
                await asyncio.sleep(0.5)
                answer = "您好，感谢您的咨询。关于您的问题，我会尽快为您解答。请稍等，我为您查询相关信息。"
            
            return answer
            
        except Exception as e:
            logger.error(f"LLM 调用失败：{e}", exc_info=True)
            # 降级处理：返回友好提示
            return "抱歉，系统暂时无法回答您的问题。请稍后再试或联系人工客服。"
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()
