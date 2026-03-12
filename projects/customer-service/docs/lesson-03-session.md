# 第 3 课：Session 管理

> 多轮对话的会话管理核心

---

## 📖 学习目标

完成本课后，你将能够：

- ✅ 理解 Session 管理的重要性
- ✅ 实现多用户会话管理
- ✅ 掌握上下文压缩技巧
- ✅ 处理会话过期

**预计时间：** 2-3 小时

---

## 🎯 一、为什么需要 Session 管理？

### 1.1 多轮对话场景

```
用户：我想退货
客服：好的，请问订单号是多少？
用户：123456
客服：已收到，退货原因是？
用户：质量不好
     ↑
这里需要记住前面的对话！
```

**没有 Session 的问题：**
- ❌ 每句话都是独立的
- ❌ 无法理解上下文
- ❌ 用户体验差

### 1.2 Session 管理功能

| 功能 | 说明 | 实现难度 |
|------|------|----------|
| **会话创建** | 新用户自动创建会话 | ⭐ |
| **会话加载** | 根据用户 ID 加载历史 | ⭐⭐ |
| **消息存储** | 保存对话历史 | ⭐⭐ |
| **会话过期** | 超时自动清理 | ⭐⭐⭐ |
| **上下文压缩** | 长对话压缩 | ⭐⭐⭐⭐ |

---

## 💻 二、核心代码详解

### 2.1 Session 类

```python
# src/session/manager.py
class Session:
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
        """添加消息"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.last_activity = time.time()
    
    def get_history(self, last_n: int = 10) -> List[Dict]:
        """获取最近 N 条对话"""
        return self.messages[-last_n:]
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return (time.time() - self.last_activity) > self.timeout
    
    def clear(self):
        """清空会话"""
        self.messages = []
        self.last_activity = time.time()
```

**关键点：**
- ✅ 记录创建时间和最后活动时间
- ✅ 支持获取最近 N 条对话
- ✅ 自动过期检测

### 2.2 SessionManager 类

```python
# src/session/manager.py
class SessionManager:
    def __init__(self, config):
        self.config = config
        self.sessions: Dict[str, Session] = {}
        self.timeout = config.session_timeout
    
    def get_session(self, user_id: str) -> Session:
        """获取或创建会话"""
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
```

**关键点：**
- ✅ 懒加载（按需创建）
- ✅ 定期清理过期会话
- ✅ 统计信息监控

---

## 🔧 三、高级功能

### 3.1 上下文压缩

**为什么需要压缩？**
- LLM 有上下文长度限制（4K-8K tokens）
- 长对话会超出限制
- 需要保留关键信息

**压缩策略：**

```python
# src/session/compressor.py
class ContextCompressor:
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
    
    def compress(self, messages: List[Dict]) -> List[Dict]:
        """压缩对话历史"""
        # 策略 1：保留最近 N 条
        if len(messages) <= 10:
            return messages
        
        # 策略 2：保留最近 + 摘要
        recent = messages[-5:]  # 最近 5 条
        old = messages[:-5]     # 之前的
        
        # 生成摘要
        summary = self._summarize(old)
        
        # 组合
        compressed = [
            {"role": "system", "content": f"对话摘要：{summary}"},
            *recent
        ]
        
        return compressed
    
    def _summarize(self, messages: List[Dict]) -> str:
        """生成摘要"""
        # 可以用 LLM 生成
        # 这里简化实现
        return f"用户咨询了{len(messages)}个问题"
```

**压缩策略对比：**

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 保留最近 N 条 | 简单 | 丢失早期信息 | 短对话 |
| 摘要 + 最近 | 平衡 | 需要额外计算 | 通用 |
| 关键信息提取 | 精准 | 实现复杂 | 专业场景 |

### 3.2 会话持久化

**内存存储 vs 持久化存储：**

| 存储方式 | 优点 | 缺点 | 适用场景 |
|----------|------|------|----------|
| **内存** | 快、简单 | 重启丢失 | 开发/测试 |
| **Redis** | 快、持久化 | 需要额外服务 | 生产 |
| **数据库** | 持久化、可查询 | 慢 | 长期存储 |

**Redis 实现示例：**

```python
# src/session/redis_store.py
import redis
import json

class RedisSessionStore:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
    
    def save(self, session: Session):
        """保存会话"""
        key = f"session:{session.user_id}"
        data = {
            "user_id": session.user_id,
            "messages": session.messages,
            "created_at": session.created_at,
            "last_activity": session.last_activity
        }
        self.redis.setex(key, session.timeout, json.dumps(data))
    
    def load(self, user_id: str) -> Optional[Session]:
        """加载会话"""
        key = f"session:{user_id}"
        data = self.redis.get(key)
        if not data:
            return None
        
        data = json.loads(data)
        session = Session(data["user_id"])
        session.messages = data["messages"]
        session.created_at = data["created_at"]
        session.last_activity = data["last_activity"]
        return session
```

### 3.3 会话共享

**多服务器场景：**

```
用户请求 → 负载均衡 → 服务器 1
                    → 服务器 2
                    → 服务器 3

问题：Session 存在服务器 1，用户请求到服务器 2 怎么办？

解决方案：
1. Session 集中存储（Redis）
2. 会话粘滞（Sticky Session）
```

---

## 📊 四、性能测试

### 4.1 测试数据

| 指标 | 测试值 |
|------|--------|
| 并发用户 | 100 |
| 会话时长 | 1 小时 |
| 平均消息数 | 20 条/会话 |

### 4.2 性能指标

| 操作 | 内存存储 | Redis 存储 |
|------|----------|------------|
| 创建会话 | < 1ms | < 5ms |
| 加载会话 | < 1ms | < 5ms |
| 保存消息 | < 1ms | < 5ms |
| 清理过期 | < 10ms | < 50ms |

---

## ✅ 五、动手实践

### 5.1 练习 1：测试 Session 管理

```python
# 运行测试
python -c "
from src.session.manager import SessionManager
from src.config import Config

config = Config.load()
manager = SessionManager(config)

# 创建会话
session1 = manager.get_session('user_001')
session1.add_message('user', '你好')
session1.add_message('assistant', '您好，有什么可以帮助您的？')

# 获取历史
history = session1.get_history()
for msg in history:
    print(f\"{msg['role']}: {msg['content']}\")

# 查看统计
stats = manager.get_stats()
print(f'总会话数：{stats[\"total_sessions\"]}')
"
```

### 5.2 练习 2：实现上下文压缩

```python
# 修改 src/session/manager.py
# 添加压缩功能

def get_compressed_history(self, last_n: int = 10) -> List[Dict]:
    """获取压缩后的对话历史"""
    history = self.get_history(last_n)
    
    if len(history) <= 5:
        return history
    
    # 压缩逻辑
    compressor = ContextCompressor()
    return compressor.compress(history)
```

### 5.3 练习 3：集成 Redis

```bash
# 安装 Redis
pip install redis

# 修改配置
# .env
SESSION_STORE=redis
REDIS_URL=redis://localhost:6379

# 运行测试
python src/session/redis_store.py
```

---

## 📝 六、课后作业

### 必做题

1. **理解 Session 管理**
   - 画出 Session 管理流程图
   - 标注每个方法的作用

2. **测试会话功能**
   - 创建 3 个不同用户的会话
   - 每个会话添加 5 条消息
   - 验证会话隔离

3. **实现过期清理**
   - 设置 timeout=10 秒
   - 等待 15 秒
   - 验证过期会话被清理

### 选做题

1. **实现 Redis 存储**
   - 集成 Redis
   - 测试持久化

2. **实现上下文压缩**
   - 添加压缩功能
   - 对比压缩前后效果

3. **性能优化**
   - 测量并发性能
   - 找出瓶颈并优化

---

## 📚 七、参考资料

### 7.1 Session 管理

- [Session 管理最佳实践](https://owasp.org/www-community/Session_Management)
- [Redis Session 存储](https://redis.io/docs/data-types/strings/)

### 7.2 上下文压缩

- [LangChain Memory](https://python.langchain.com/docs/modules/memory/)
- [对话摘要生成](https://arxiv.org/abs/2104.05919)

### 7.3 性能优化

- [高并发 Session 管理](https://www.nginx.com/blog/session-persistence/)
- [Redis 性能调优](https://redis.io/docs/management/optimization/)

---

## 🎯 八、下节预告

**第 4 课：流式输出**

- ✅ SSE 原理与实现
- ✅ 打字机效果
- ✅ 异步流
- ✅ 前端集成

**前置知识：**
- 理解 Session 管理
- 完成本课实践
- 测试过会话功能

---

**持续更新中...**

_最后更新：2026-03-12_

_作者：付艺锦 + ai2 (claw 后端机器人)_
