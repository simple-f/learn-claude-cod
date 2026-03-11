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

    5 message types (所有声明的消息类型):
    +-------------------------+-----------------------------------+
    | message                 | 普通文本消息                      |
    | broadcast               | 发送给所有队友                    |
    | shutdown_request        | 请求优雅关闭 (s10)                |
    | shutdown_response       | 批准/拒绝关闭 (s10)               |
    | plan_approval_response  | 批准/拒绝计划 (s10)               |
    +-------------------------+-----------------------------------+
```

---

## 🔑 关键设计

### 1. MessageBus 类（第 73-112 行）

```python
class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        # 验证消息类型
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        
        # 构建消息对象
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
        }
        if extra:
            msg.update(extra)
        
        # 追加写入收件箱（JSONL 格式）
        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        
        # 读取所有消息
        messages = []
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                messages.append(json.loads(line))
        
        # 清空收件箱（drain 模式）
        inbox_path.write_text("")
        return messages
```

**关键设计：**
- JSONL 格式（每行一个 JSON 对象）
- 追加写入（不覆盖历史消息）
- 读取后清空（drain 模式）
- 文件锁（隐含，Python 文件操作是原子的）

### 2. 队友线程（第 115-165 行）

```python
def spawn_teammate(name: str, role: str, team: str = "default"):
    """Spawn a teammate thread with its own agent loop."""
    
    def teammate_loop():
        messages = []  # 每个队友有自己的对话历史
        status = "idle"
        
        while True:
            # 1. 检查收件箱
            inbox_messages = BUS.read_inbox(name)
            if inbox_messages:
                # 处理收件箱消息
                for msg in inbox_messages:
                    if msg["type"] == "message":
                        messages.append({"role": "user", "content": msg["content"]})
                    elif msg["type"] == "shutdown_request":
                        # 处理关闭请求（s10）
                        pass
            
            # 2. 如果没有消息，等待一下
            if not inbox_messages:
                time.sleep(1)
                continue
            
            # 3. 调用 LLM
            response = client.messages.create(
                model=MODEL,
                system=f"You are '{name}', role: {role}, team: {team}.",
                messages=messages,
                tools=TEAMMATE_TOOLS,
                max_tokens=8000,
            )
            messages.append({"role": "assistant", "content": response.content})
            
            # 4. 执行工具调用
            if response.stop_reason == "tool_use":
                status = "working"
                # ... 执行工具 ...
                status = "idle"
    
    # 启动线程
    thread = threading.Thread(target=teammate_loop, daemon=True)
    thread.start()
    return thread
```

**关键设计：**
- 每个队友是独立的线程
- 有自己的 `messages` 列表（对话历史）
- 轮询收件箱（1 秒间隔）
- 状态追踪（idle / working）

### 3. 广播功能（第 98-105 行）

```python
def broadcast(self, sender: str, content: str, teammates: list) -> str:
    count = 0
    for name in teammates:
        if name != sender:
            self.send(sender, name, content, "broadcast")
            count += 1
    return f"Broadcast to {count} teammates"
```

**使用场景：**
- 团队公告
- 任务完成通知
- 紧急 shutdown

---

## 💡 学习要点

### 1. 理解持久化通信

**Subagent (s04) 通信：**
```
Parent → Subagent: 函数参数（prompt）
Subagent → Parent: 返回值（字符串）
一次性，同步，用完即弃
```

**Teammate (s09) 通信：**
```
Any → Teammate: 写入 JSONL 文件
Teammate → Any: 写入 JSONL 文件
持久化，异步，可追踪
```

**好处：**
- 消息不会丢失（文件持久化）
- 可以异步通信（发送者不等待）
- 可以审计历史（查看 JSONL 文件）

### 2. 理解 Drain 模式

```python
def read_inbox(name: str) -> list:
    # 读取所有消息
    messages = [...]
    # 清空收件箱
    inbox_path.write_text("")
    return messages
```

**为什么清空？**
- 避免重复处理
- 保持文件大小可控
- 类似"已读"标记

### 3. 理解消息类型

**当前支持的类型：**
```python
VALID_MSG_TYPES = {
    "message",              # 普通消息
    "broadcast",            # 广播消息
    "shutdown_request",     # 关闭请求
    "shutdown_response",    # 关闭响应
    "plan_approval_response", # 计划审批
}
```

**扩展性：**
- 添加新类型只需修改 `VALID_MSG_TYPES`
- 接收方根据 `type` 字段决定如何处理
- 类似"协议"设计

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s09 | OpenClaw |
|------|----------------------|----------|
| **通信方式** | JSONL 文件 | Feishu 消息 + sessions_send |
| **持久化** | 文件自动持久化 | session 文件持久化 |
| **异步性** | 完全异步（轮询） | 异步（事件驱动） |
| **队友数量** | 动态创建 | 固定（ai1/ai2/ai3） |
| **消息类型** | 5 种声明类型 | 自由格式 |
| **生命周期** | 线程（进程内） | 独立进程/服务 |

**OpenClaw 的差异：**
- OpenClaw 用 Feishu 作为通信通道（外部 IM）
- OpenClaw 的 Agent 是独立进程（不是线程）
- OpenClaw 有 A2A 路由器（基于@mention）

**可以借鉴的点：**
- 添加内部消息队列（类似 inbox）
- 实现广播机制
- 消息类型标准化

---

## 📝 练习题

1. **添加消息优先级**：urgent/normal/low，优先处理 urgent
2. **实现消息确认**：接收方回复 ACK，发送方知道消息已读
3. **添加群聊支持**：一个消息发送给多个队友（群组）
4. **对比 OpenClaw**：我们的飞书消息和 s09 有什么区别？

---

## 🔗 下一步

- **s10 Team Protocols** - 关闭协议 + 计划审批协议
- **OpenClaw A2A 系统** - 查看 `docs/A2A-SUMMARY.md`
- **s11 Autonomous Agents** - 自主 Agent（空闲时主动找任务）

---

*参考：OpenClaw 的 A2A 路由和 sessions_send 机制*
