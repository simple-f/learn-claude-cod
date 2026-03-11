# s08 Background Tasks - 学习笔记

## 📌 核心洞察

> **"Fire and forget -- the agent doesn't block while the command runs."**

这是 s08 最重要的设计思想：**后台执行耗时任务，Agent 不需要阻塞等待**。

---

## 🏗️ 架构图

```
主线程                     后台线程
+-----------------+        +-----------------+
| agent loop      |        | task executes   |
| ...             |        | ...             |
| [LLM call] <---+------- | enqueue(result) |
|  ^drain queue   |        +-----------------+
+-----------------+

时间线：
Agent ----[spawn A]----[spawn B]----[other work]----
             |              |
             v              v
          [A runs]      [B runs]        (并行执行)
             |              |
             +-- notification queue --> [results injected]
```

---

## 🔑 BackgroundManager 类（第 32-84 行）

### 1. 启动后台任务

```python
def run(self, command: str) -> str:
    """Start a background thread, return task_id immediately."""
    task_id = str(uuid.uuid4())[:8]  # 8 位短 ID
    self.tasks[task_id] = {
        "status": "running", 
        "result": None, 
        "command": command
    }
    
    thread = threading.Thread(
        target=self._execute, 
        args=(task_id, command), 
        daemon=True  # 守护线程（主程序退出时自动终止）
    )
    thread.start()
    
    return f"Background task {task_id} started: {command[:80]}"
```

**关键点：**
- 立即返回 task_id（不阻塞）
- 守护线程（daemon=True）
- 命令截断显示（前 80 字符）

### 2. 执行任务（后台线程）

```python
def _execute(self, task_id: str, command: str):
    """Thread target: run subprocess, capture output, push to queue."""
    try:
        r = subprocess.run(
            command, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=300  # 5 分钟超时
        )
        output = (r.stdout + r.stderr).strip()[:50000]
        status = "completed"
    except subprocess.TimeoutExpired:
        output = "Error: Timeout (300s)"
        status = "timeout"
    except Exception as e:
        output = f"Error: {e}"
        status = "error"
    
    # 更新任务状态
    self.tasks[task_id]["status"] = status
    self.tasks[task_id]["result"] = output or "(no output)"
    
    # 推送到通知队列（主线程会来取）
    with self._lock:
        self._notification_queue.append({
            "task_id": task_id,
            "status": status,
            "command": command[:80],
            "result": (output or "(no output)")[:500],  # 只通知前 500 字符
        })
```

**关键设计：**
- 300 秒超时（5 分钟）
- 输出截断（50000 字符）
- 通知队列（线程安全）

### 3. 检查任务状态

```python
def check(self, task_id: str = None) -> str:
    """Check status of one task or list all."""
    if task_id:
        t = self.tasks.get(task_id)
        if not t:
            return f"Error: Unknown task {task_id}"
        return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"
    
    # 列出所有任务
    lines = []
    for tid, t in self.tasks.items():
        lines.append(f"{tid}: [{t['status']}] {t['command'][:60]}")
    return "\n".join(lines) if lines else "No background tasks."
```

### 4. 排出通知队列

```python
def drain_notifications(self) -> list:
    """Return and clear all pending completion notifications."""
    with self._lock:
        notifs = list(self._notification_queue)
        self._notification_queue.clear()
    return notifs
```

**主线程如何使用：**
```python
# 在调用 LLM 之前，先排出通知
notifications = BG.drain_notifications()
if notifications:
    for notif in notifications:
        messages.append({
            "role": "user",
            "content": f"Background task {notif['task_id']} completed: {notif['result']}"
        })
```

---

## 💡 学习要点

### 1. 理解线程模型

```
主线程（Agent Loop）          后台线程 1          后台线程 2
      |                           |                  |
      |-- spawn A --------------->|                  |
      |                           |-- run command    |
      |                           |                  |
      |-- spawn B ---------------------------------->|
      |                           |                  |-- run command
      |                           |                  |
      |-- do other work           |                  |
      |                           |                  |
      |<-- notification ----------+------------------+
      |                           |                  |
      |-- drain notifications     |                  |
```

**关键点：**
- 主线程不等待
- 多个后台任务并行
- 通知队列解耦

### 2. 理解线程安全

```python
self._lock = threading.Lock()

# 写入通知队列（后台线程）
with self._lock:
    self._notification_queue.append({...})

# 读取通知队列（主线程）
with self._lock:
    notifs = list(self._notification_queue)
    self._notification_queue.clear()
```

**为什么需要锁？**
- 避免同时读写导致数据损坏
- Python 的 list 不是线程安全的
- 简单但有效

### 3. 理解超时处理

```python
timeout=300  # 5 分钟
```

**为什么设置超时？**
- 防止无限运行的任务
- 释放线程资源
- 给用户明确反馈

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s08 | OpenClaw |
|------|----------------------|----------|
| **后台执行** | threading.Thread | 无（同步执行） |
| **通知机制** | 队列 + drain | 无 |
| **超时控制** | 300 秒 | 120 秒（bash 工具） |
| **并行度** | 多任务并行 | 单任务串行 |
| **状态查询** | check 工具 | 无 |

**OpenClaw 的差异：**
- OpenClaw 是同步执行（等待工具完成）
- OpenClaw 的 Heartbeat 是定时触发（不是后台任务）
- OpenClaw 可以借鉴 s08 实现并行任务

**可以借鉴的点：**
- 添加后台执行工具
- 支持长时间运行的任务
- 通知队列机制

---

## 📝 练习题

1. **添加进度报告**：后台任务定期更新进度
2. **添加取消功能**：`cancel(task_id)` 终止任务
3. **添加重试机制**：失败的任务自动重试
4. **对比 OpenClaw**：我们的 bash 工具和 s08 有什么区别？

---

## 🔗 下一步

- **s11 Autonomous Agents** - 自主 Agent（后台执行 + 任务认领）
- **OpenClaw sessions_spawn** - 对比子进程执行
- **Python threading 文档** - 深入学习线程编程

---

*参考：Python threading 模块和 subprocess 模块文档*
