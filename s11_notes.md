# s11 Autonomous Agents - 学习笔记

## 📌 核心洞察

> **"The agent finds work itself."**

这是 s11 最重要的设计思想：**Agent 是自主的——它自己寻找工作，而不是被动等待指令**。

---

## 🏗️ Agent 生命周期

```
+-------+
| spawn |
+---+---+
    |
    v
+-------+  tool_use    +-------+
| WORK  | <----------- |  LLM  |
+---+---+              +-------+
    |
    | stop_reason != tool_use
    v
+--------+
| IDLE   | poll every 5s for up to 60s
+---+----+
    |
    +---> check inbox → message? → resume WORK
    |
    +---> scan .tasks/ → unclaimed? → claim → resume WORK
    |
    +---> timeout (60s) → shutdown
```

---

## 🔑 关键机制

### 1. 空闲循环（Idle Cycle）

```python
def idle_cycle(teammate_name: str) -> bool:
    """
    空闲时轮询工作，返回 True 表示找到工作继续工作，False 表示超时关闭
    """
    start_time = time.time()
    
    while time.time() - start_time < IDLE_TIMEOUT:  # 60 秒超时
        # 1. 检查收件箱
        messages = BUS.read_inbox(teammate_name)
        if messages:
            # 有新消息 → 恢复工作
            return True
        
        # 2. 扫描未认领的任务
        unclaimed = scan_unclaimed_tasks()
        if unclaimed:
            # 有未认领任务 → 认领一个
            task = unclaimed[0]
            claim_task(task["id"], teammate_name)
            print(f"[{teammate_name}] claimed task #{task['id']}")
            return True
        
        # 3. 等待一下再轮询
        time.sleep(POLL_INTERVAL)  # 5 秒
    
    # 超时 → 关闭
    print(f"[{teammate_name}] idle timeout, shutting down")
    return False
```

**轮询策略：**
- 每 5 秒检查一次
- 最多等待 60 秒
- 超时自动关闭（节省资源）

### 2. 任务认领（第 92-103 行）

```python
def scan_unclaimed_tasks() -> list:
    """扫描所有未认领的待办任务"""
    TASKS_DIR.mkdir(exist_ok=True)
    unclaimed = []
    for f in sorted(TASKS_DIR.glob("task_*.json")):
        task = json.loads(f.read_text())
        if (task.get("status") == "pending"
                and not task.get("owner")
                and not task.get("blockedBy")):  # 没有被阻塞
            unclaimed.append(task)
    return unclaimed


def claim_task(task_id: int, owner: str) -> str:
    """认领任务（加锁防止重复认领）"""
    with _claim_lock:
        path = TASKS_DIR / f"task_{task_id}.json"
        if not path.exists():
            return f"Error: Task {task_id} not found"
        task = json.loads(path.read_text())
        task["owner"] = owner
        task["status"] = "in_progress"
        path.write_text(json.dumps(task, indent=2))
    return f"Claimed task #{task_id} for {owner}"
```

**认领条件：**
- `status == "pending"` - 待办状态
- `owner == ""` - 没有人认领
- `blockedBy == []` - 没有被阻塞（依赖的任务都完成了）

**线程安全：**
```python
_claim_lock = threading.Lock()  # 防止多个 Agent 同时认领同一个任务
```

### 3. 身份重新注入（第 106-120 行）

```python
def create_identity_block(name: str, role: str, team: str) -> dict:
    """创建身份块，用于上下文压缩后重新注入"""
    return {
        "role": "user",
        "content": f"""You are '{name}', role: {role}, team: {team}.

Your responsibilities:
- Complete tasks assigned to you
- Communicate via inbox messages
- Shutdown gracefully when requested

Remember your identity even after context compression."""
    }


# 压缩后重新注入
messages = [create_identity_block("alice", "coder", "default"), ...remaining...]
```

**为什么需要身份注入？**
- 上下文压缩后可能丢失角色信息
- Agent 需要记住"我是谁"
- 保持行为一致性

---

## 💡 学习要点

### 1. 理解自主性

**被动 Agent（之前）：**
```
用户提问 → Agent 回答 → 结束
```

**自主 Agent（s11）：**
```
用户提问 → Agent 回答 → 空闲 → 主动找任务 → 执行 → 空闲 → ...
```

**关键差异：**
- 不需要人类持续输入
- 自己寻找工作
- 持续运行直到超时

### 2. 理解任务板模式

```
.tasks/
  task_1.json  [x] 设计数据库 (owner: alice, completed)
  task_2.json  [>] 实现认证 (owner: bob, in_progress)
  task_3.json  [ ] 创建页面 (owner: "", pending) ← 可认领
  task_4.json  [ ] 写测试 (blockedBy: [2], pending) ← 被阻塞
```

**任务板优势：**
- 去中心化（不需要中央调度器）
- 自主认领（Agent 自己决定做什么）
- 依赖管理（blockedBy 确保顺序）

### 3. 理解优雅关闭

```python
IDLE_TIMEOUT = 60  # 60 秒无工作 → 关闭

while time.time() - start_time < IDLE_TIMEOUT:
    if has_work():
        return True  # 继续工作
    time.sleep(POLL_INTERVAL)

return False  # 超时关闭
```

**为什么设置超时？**
- 避免无限空转（浪费资源）
- 自动清理闲置 Agent
- 符合"用完即走"原则

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s11 | OpenClaw |
|------|----------------------|----------|
| **自主性** | 主动认领任务 | 被动响应（@mention 触发） |
| **任务分配** | 任务板 + 认领 | A2A 路由（手动分配） |
| **空闲处理** | 轮询 60 秒超时 | 常驻进程（心跳检查） |
| **身份管理** | 身份块重新注入 | SOUL.md + IDENTITY.md |
| **关闭机制** | 空闲超时 + shutdown_request | 手动停止/重启 |

**OpenClaw 的差异：**
- OpenClaw 是**常驻服务**（不超时关闭）
- OpenClaw 用**心跳机制**主动检查（邮件、日历等）
- OpenClaw 的 A2A 是**基于@mention**（不是自主认领）

**可以借鉴的点：**
- 添加任务认领机制
- 实现空闲超时关闭
- 身份重新注入（压缩后恢复）

---

## 📝 练习题

1. **添加任务优先级**：优先认领高优先级任务
2. **添加技能匹配**：只认领自己擅长类型的任务
3. **添加协作认领**：多个 Agent 合作完成大任务
4. **对比 OpenClaw**：我们的 HEARTBEAT 和 s11 空闲循环有什么区别？

---

## 🔗 下一步

- **s12 Worktree Isolation** - 任务环境隔离（如果存在）
- **OpenClaw HEARTBEAT.md** - 对比自主检查机制
- **OpenClaw A2A 系统** - 对比任务分配方式

---

*参考：OpenClaw 的 HEARTBEAT.md、A2A 路由和 session 管理系统*
