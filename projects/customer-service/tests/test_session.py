#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session 管理测试

测试内容：
- 会话创建
- 消息存储
- 会话过期
- 会话清理
"""

import pytest
import time
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.session.manager import SessionManager, Session
from src.config import Config


@pytest.fixture
def config():
    """配置对象"""
    return Config.load()


@pytest.fixture
def session_manager(config):
    """Session 管理器"""
    return SessionManager(config)


class TestSession:
    """Session 类测试"""
    
    def test_create_session(self):
        """测试创建会话"""
        session = Session("user_001", timeout=3600)
        
        assert session.user_id == "user_001", "用户 ID 错误"
        assert session.timeout == 3600, "超时时间错误"
        assert len(session.messages) == 0, "初始消息应为空"
        print("✅ 会话创建成功")
    
    def test_add_message(self):
        """测试添加消息"""
        session = Session("user_001")
        
        session.add_message("user", "你好")
        session.add_message("assistant", "您好")
        
        assert len(session.messages) == 2, "消息数量错误"
        assert session.messages[0]["role"] == "user", "角色错误"
        assert session.messages[0]["content"] == "你好", "内容错误"
        print("✅ 消息添加成功")
    
    def test_get_history(self):
        """测试获取历史"""
        session = Session("user_001")
        
        # 添加 10 条消息
        for i in range(10):
            session.add_message("user", f"消息{i}")
        
        # 获取最近 5 条
        history = session.get_history(last_n=5)
        assert len(history) == 5, "历史数量错误"
        assert history[-1]["content"] == "消息 9", "最后一条消息错误"
        print("✅ 历史获取成功")
    
    def test_session_expiry(self):
        """测试会话过期"""
        # 创建 1 秒过期的会话
        session = Session("user_001", timeout=1)
        
        assert not session.is_expired(), "新会话不应过期"
        
        time.sleep(1.1)
        
        assert session.is_expired(), "会话应已过期"
        print("✅ 会话过期检测成功")
    
    def test_clear_session(self):
        """测试清空会话"""
        session = Session("user_001")
        session.add_message("user", "测试")
        
        session.clear()
        
        assert len(session.messages) == 0, "会话未清空"
        print("✅ 会话清空成功")


class TestSessionManager:
    """Session 管理器测试"""
    
    def test_get_session(self, session_manager):
        """测试获取会话"""
        session = session_manager.get_session("user_001")
        
        assert session is not None, "会话创建失败"
        assert session.user_id == "user_001", "用户 ID 错误"
        print("✅ 会话获取成功")
    
    def test_session_cache(self, session_manager):
        """测试会话缓存"""
        session1 = session_manager.get_session("user_001")
        session2 = session_manager.get_session("user_001")
        
        assert session1 is session2, "应返回同一会话实例"
        print("✅ 会话缓存成功")
    
    def test_multiple_sessions(self, session_manager):
        """测试多会话"""
        session1 = session_manager.get_session("user_001")
        session2 = session_manager.get_session("user_002")
        
        assert session1 is not session2, "不同用户应有不同会话"
        print("✅ 多会话管理成功")
    
    def test_get_stats(self, session_manager):
        """测试统计信息"""
        session_manager.get_session("user_001")
        session_manager.get_session("user_002")
        
        stats = session_manager.get_stats()
        
        assert stats["total_sessions"] == 2, "总会话数错误"
        assert "active_sessions" in stats, "缺少活跃会话数"
        print(f"✅ 统计信息：{stats}")
    
    def test_cleanup_expired(self, session_manager):
        """测试过期清理"""
        # 创建 1 秒过期的会话
        session_manager.sessions["user_001"] = Session("user_001", timeout=1)
        
        time.sleep(1.1)
        
        session_manager.cleanup_expired()
        
        assert "user_001" not in session_manager.sessions, "过期会话未清理"
        print("✅ 过期清理成功")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
