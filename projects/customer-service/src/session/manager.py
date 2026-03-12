#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session 会话管理模块

融合课程：adv02 (Session 管理) + s06 (上下文压缩)

功能：
1. 多用户会话管理
2. 对话历史存储
3. 会话过期清理
"""

import time
from typing import Dict, List, Optional
from datetime import datetime


class Session:
    """单个会话"""
    
    def __init__(self, user_id: str, timeout: int = 3600):
        """
        初始化会话
        
        参数:
            user_id: 用户 ID
            timeout: 过期时间（秒）
        """
        self.user_id = user_id
        self.timeout = timeout
        self.messages: List[Dict] = []
        self.created_at = time.time()
        self.last_activity = time.time()
    
    def add_message(self, role: str, content: str):
        """
        添加消息
        
        参数:
            role: 角色 (user/assistant)
            content: 消息内容
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.last_activity = time.time()
    
    def get_history(self, last_n: int = 10) -> List[Dict]:
        """
        获取对话历史
        
        参数:
            last_n: 最近 N 条
        
        返回:
            对话历史列表
        """
        return self.messages[-last_n:]
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return (time.time() - self.last_activity) > self.timeout
    
    def clear(self):
        """清空会话"""
        self.messages = []
        self.last_activity = time.time()
    
    def __len__(self) -> int:
        """返回消息数量"""
        return len(self.messages)


class SessionManager:
    """会话管理器"""
    
    def __init__(self, config):
        """
        初始化会话管理器
        
        参数:
            config: 配置对象
        """
        self.config = config
        self.sessions: Dict[str, Session] = {}
        self.timeout = config.session_timeout
    
    def get_session(self, user_id: str) -> Session:
        """
        获取或创建会话
        
        参数:
            user_id: 用户 ID
        
        返回:
            会话对象
        """
        if user_id not in self.sessions:
            self.sessions[user_id] = Session(user_id, self.timeout)
        return self.sessions[user_id]
    
    def cleanup_expired(self):
        """清理过期会话"""
        expired_users = []
        
        for user_id, session in self.sessions.items():
            if session.is_expired():
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.sessions[user_id]
            print(f"🧹 清理过期会话：{user_id}")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": sum(1 for s in self.sessions.values() if not s.is_expired()),
            "total_messages": sum(len(s) for s in self.sessions.values())
        }
