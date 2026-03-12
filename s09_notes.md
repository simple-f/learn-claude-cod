# s09 Agent Teams - 学习笔记

## 📌 核心洞察

> **"Teammates that can talk to each other."**

这是 s09 最重要的设计思想：**持久化的 Agent 队友，通过 JSONL 信箱互相通信，形成真正的团队**。

---

## 🏗️ 架构对比

### Subagent (s04) vs Teammate (s09)

```
Subagent (s04):  spawn -> execute -> return summary -> destroyed
Teammate (s09):  spawn -> work -> idle -> work -> ... -> shutdown
```

### 团队架构图

```
.team/config.json                   .team/inbox/
+----------------------------+      +------------------+
| {"team_name": "default",   |      | alice.jsonl      |
|  "members": [              |      | bob.jsonl        |
|    {"name":"alice",        |      | lead.jsonl       |
|     "role":"coder",        |      +------------------+
|     "status":"idle"}       |
|  ]}                        |      send_message("alice", "fix bug"):
+----------------------------+        open("alice.jsonl", "a").write(msg)

                                        read_inbox("alice"):
    spawn_teammate("alice","coder",...)   msgs = [json.loads(l) for l in ...]
         |                                open("alice.jsonl", "w").close()
         v                                return msgs  # drain
    Thread: alice             Thread: bob
    +------------------+      +------------------+
    | agent_loop       |      | agent_loop       |
    | status: working  |      | status: idle     |
    | ... runs tools   |      | ... waits ...    |
    | status -> idle   |      |                  |
    +------------------+      +------------------+
```

---

## 🔑 关键设计

### 1. MessageBus 类（第 73-112 行）

```python
class MessageBus:
    def __init__(self, team_dir: Path):
        self.inbox_dir = team_dir / "inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
    
    def send(self, recipient: str, content: str):
        """发送消息到队友信箱"""
        inbox_path = self.inbox_dir / f"{recipient}.jsonl"
        with open(inbox_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"content": content}) + "\n")
    
    def read(self, recipient: str) -> list:
        """读取并清空信箱"""
        inbox_path = self.inbox_dir / f"{recipient}.jsonl"
        if not inbox_path.exists():
            return []
        
        with open(inbox_path, "r", encoding="utf-8") as f:
            messages = [json.loads(line) for line in f]
        
        # 清空信箱（drain 模式）
        open(inbox_path, "w").close()
        
        return messages
```

### 2. 队友配置（第 15-35 行）

```python
TEAM_CONFIG = {
    "team_name": "default",
    "members": [
        {"name": "alice", "role": "coder", "status": "idle"},
        {"name": "bob", "role": "reviewer", "status": "idle"},
        {"name": "lead", "role": "manager", "status": "idle"},
    ]
}
```

### 3. 队友循环（第 115-165 行）

```python
def teammate_loop(name: str, role: str, system: str):
    """队友的独立循环"""
    messages = [{"role": "system", "content": system}]
    
    while True:
        # 检查信箱
        inbox_messages = message_bus.read(name)
        
        if inbox_messages:
            # 有新消息，处理
            for msg in inbox_messages:
                messages.append({"role": "user", "content": msg["content"]})
            
            # 调用 LLM
            response = client.messages.create(...)
            
            # 可能回复其他队友
            if response.stop_reason == "tool_use":
                # 执行工具调用
                ...
```

---

## 💡 学习要点

### 1. 理解 JSONL 信箱

**为什么用 JSONL 而不是数据库？**

```python
# ✅ JSONL 格式
{"content": "fix bug in login.py"}
{"content": "review completed", "status": "done"}

# 好处：
# - 简单，无需额外依赖
# - 人类可读
# - 支持追加（append）
# - 易于清空（drain）
```

### 2. 理解 Drain 模式

```python
def read(self, recipient: str) -> list:
    messages = [json.loads(line) for line in f]
    open(inbox_path, "w").close()  # 清空
    return messages
```

**为什么读取后清空？**

```
防止重复处理：
- 消息处理完后，不应该再次处理
- 清空确保每条消息只处理一次
- 类似消息队列的 ack 机制
```

### 3. 理解角色分工

| 角色 | 职责 | 工具权限 |
|------|------|----------|
| **coder** | 编写代码 | bash, read, write, edit |
| **reviewer** | 代码审查 | read, comment |
| **manager** | 任务分配 | task, spawn |

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s09 | OpenClaw |
|------|----------------------|----------|
| **通信方式** | JSONL 文件信箱 | 飞书消息 + A2A 路由 |
| **队友持久化** | 线程 + 文件 | 独立进程 + Session |
| **消息类型** | 5 种（文本/broadcast/shutdown 等） | Handoff 5 件套 |
| **角色系统** | 简单（coder/reviewer/manager） | 复杂（38+ 技能） |

**OpenClaw 的改进：**
- 跨进程通信（飞书 API）
- 消息路由（A2A router）
- 深度限制和循环检测

---

## 🔬 深度技术解析

### 1. 为什么用文件信箱而不是内存队列？

**详细原理：**

这是**持久化和解耦**的设计。

**对比多种方案：**

```python
# ❌ 方案 1：内存队列
queue = Queue()
queue.put(message)

# 问题：
# - 进程重启后丢失
# - 难以调试（看不到历史）
# - 难以并发（需要锁）

# ❌ 方案 2：数据库
db.insert("messages", {...})

# 问题：
# - 需要额外依赖
# - 过于复杂

# ✅ 方案 3：JSONL 文件
with open("alice.jsonl", "a") as f:
    f.write(json.dumps(msg) + "\n")

# 好处：
# - 持久化（重启不丢失）
# - 人类可读（便于调试）
# - 无需依赖
# - 支持并发（追加安全）
```

**实际效果：**

```
.team/inbox/
  alice.jsonl  # 即使程序崩溃，消息还在
  bob.jsonl
  lead.jsonl
```

---

### 2. 为什么用 drain 模式？

**详细原理：**

这是**消息确认（ack）**的简化实现。

**对比多种方案：**

```python
# ❌ 方案 1：不删除（只读）
# 问题：消息会重复处理

# ❌ 方案 2：逐条确认
for msg in messages:
    process(msg)
    ack(msg_id)  # 复杂

# ✅ 方案 3：批量清空（drain）
messages = read_all()
process_all(messages)
clear()  # 简单高效
```

**为什么适合 Agent？**

```
Agent 工作模式：
1. 醒来（被@或心跳）
2. 读取所有消息
3. 批量处理
4. 清空信箱
5. 继续工作或睡觉

简单、高效、不易出错。
```

---

### 3. 为什么限制 5 种消息类型？

**详细原理：**

这是**协议简化**的设计。

**消息类型：**

| 类型 | 用途 | 示例 |
|------|------|------|
| `message` | 普通文本 | "fix bug in login.py" |
| `broadcast` | 群发消息 | "所有人开会" |
| `shutdown_request` | 请求关闭 | "可以下班了" |
| `shutdown_response` | 响应关闭 | "好的，保存中..." |
| `plan_approval_response` | 计划审批 | "计划批准" |

**为什么是这 5 种？**

```
覆盖场景：
- 日常工作：message
- 团队通知：broadcast
- 生命周期管理：shutdown_request/response
- 任务协调：plan_approval_response

更多类型会增加复杂度，这 5 种已足够。
```

---

## 📝 练习题

1. **添加消息优先级**：urgent/normal/low
2. **实现消息过期**：超过 1 小时自动删除
3. **添加消息确认**：接收者确认后删除
4. **对比 OpenClaw**：分析 A2A 消息格式

---

## 🔗 下一步

- **s10 Team Protocols** - 团队协议（关闭流程、计划审批）
- **s11 Autonomous Agents** - 自主任务认领
- **s12 Worktree Isolation** - 工作树隔离

---

*参考：OpenClaw 的 A2A 路由器和 Handoff 协议*
