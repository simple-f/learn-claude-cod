#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能客服系统 - Web 服务器

提供 REST API 和 Web 界面

使用方法：
    python src/web_server.py
"""

import asyncio
import logging
import json
from typing import Dict
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agent import CustomerServiceAgent
from src.config import Config

# 配置日志
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="智能客服系统",
    description="基于 RAG 的智能客服 API",
    version="1.0.0"
)

# 全局变量
agent = None


class ChatRequest(BaseModel):
    """聊天请求"""
    user_id: str
    message: str


class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str
    intent: str
    knowledge_count: int


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    global agent
    
    logger.info("启动智能客服系统...")
    
    # 加载配置
    config = Config.load()
    config.setup_logging()
    
    # 初始化 Agent
    agent = CustomerServiceAgent(config)
    agent.load_knowledge(config.knowledge_path)
    
    logger.info("智能客服系统启动成功")


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "智能客服系统",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "agent_stats": agent.get_stats() if agent else {}
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    
    参数:
        user_id: 用户 ID
        message: 用户消息
    
    返回:
        回答、意图、知识数量
    """
    if not agent:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    try:
        # 处理对话
        answer = await agent.chat(request.user_id, request.message)
        
        # 获取意图（简化实现）
        intent = agent.intent_matcher.match(request.message)
        
        return ChatResponse(
            answer=answer,
            intent=intent,
            knowledge_count=0
        )
        
    except Exception as e:
        logger.error(f"聊天接口错误：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式聊天接口
    
    参数:
        user_id: 用户 ID
        message: 用户消息
    
    返回:
        SSE 流
    """
    if not agent:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    async def generate():
        try:
            answer = await agent.chat(request.user_id, request.message)
            
            # 逐字输出
            for char in answer:
                yield f"data: {json.dumps({'text': char})}\n\n"
                await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(f"流式聊天错误：{e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    if not agent:
        raise HTTPException(status_code=503, detail="服务未就绪")
    
    return {
        "agent": agent.get_stats(),
        "session": agent.session_manager.get_stats()
    }


@app.post("/api/feedback")
async def submit_feedback(user_id: str, rating: int, comment: str = None):
    """
    提交反馈
    
    参数:
        user_id: 用户 ID
        rating: 评分（1-5）
        comment: 评论
    """
    # TODO: 保存到数据库
    logger.info(f"用户反馈：user_id={user_id}, rating={rating}, comment={comment}")
    
    return {"status": "success"}


# 简单的 Web 界面
@app.get("/web", response_class=HTMLResponse)
async def web_interface():
    """Web 界面"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>智能客服系统</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            #chat { border: 1px solid #ccc; border-radius: 5px; padding: 20px; height: 400px; overflow-y: auto; margin-bottom: 20px; }
            .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
            .user { background-color: #e3f2fd; text-align: right; }
            .assistant { background-color: #f5f5f5; }
            input { width: 70%; padding: 10px; border: 1px solid #ccc; border-radius: 5px; }
            button { width: 25%; padding: 10px; background-color: #2196F3; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background-color: #1976D2; }
        </style>
    </head>
    <body>
        <h1>🤖 智能客服系统</h1>
        <div id="chat"></div>
        <div>
            <input id="input" placeholder="输入问题..." onkeypress="if(event.keyCode===13) send()">
            <button onclick="send()">发送</button>
        </div>
        
        <script>
            const chat = document.getElementById('chat');
            const input = document.getElementById('input');
            
            async function send() {
                const message = input.value.trim();
                if (!message) return;
                
                // 显示用户消息
                chat.innerHTML += `<div class="message user">👤 ${message}</div>`;
                input.value = '';
                chat.scrollTop = chat.scrollHeight;
                
                // 显示等待提示
                chat.innerHTML += `<div class="message assistant" id="waiting">🤖 思考中...</div>`;
                chat.scrollTop = chat.scrollHeight;
                
                try {
                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: 'web_user', message: message})
                    });
                    
                    const data = await response.json();
                    
                    // 移除等待提示
                    document.getElementById('waiting').remove();
                    
                    // 显示回答
                    chat.innerHTML += `<div class="message assistant">🤖 ${data.answer}</div>`;
                    chat.scrollTop = chat.scrollHeight;
                    
                } catch (error) {
                    document.getElementById('waiting').innerHTML = `🤖 错误：${error.message}`;
                }
            }
        </script>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    import uvicorn
    
    config = Config.load()
    
    print("=" * 60)
    print("🤖 智能客服系统 - Web 服务器")
    print("=" * 60)
    print(f"\n📍 Web 界面：http://localhost:{config.web_port}/web")
    print(f"📍 API 文档：http://localhost:{config.web_port}/docs")
    print(f"📍 健康检查：http://localhost:{config.web_port}/health")
    print("\n按 Ctrl+C 停止服务\n")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.web_port,
        log_level=config.log_level.lower()
    )
