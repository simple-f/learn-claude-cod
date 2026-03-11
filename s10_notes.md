# s10 Team Protocols - 学习笔记

## 📌 核心洞察

> **"Same request_id correlation pattern, two domains."**

这是 s10 最重要的设计思想：**同一个 request_id 关联模式，应用于两个不同的领域——关闭协议和计划审批协议**。

---

## 🏗️ 协议架构图

### 1. 关闭协议（Shutdown Protocol）

```
Shutdown FSM: pending → approved | rejected

Lead                              Teammate
+---------------------+          +---------------------+
| shutdown_request     |          |                     |
| {                    | -------> | receives request    |
|   request_id: abc    |          | decides: approve?   |
| }                    |          |                     |
+---------------------+          +---------------------+
                                         |
+---------------------+          +-------v-------------+
| shutdown_response    | <------- | shutdown_response   |
| {                    |          | {                   |
|   request_id: abc    |          |   request_id: abc   |
|   approve: true      |          |   approve: true     |
| }                    |          | }                   |
+---------------------+          +---------------------+
        |
        v
status -> "shutdown", thread stops
```

### 2. 计划审批协议（Plan Approval Protocol）

```
Plan approval FSM: pending → approved | rejected

Teammate                          Lead
+---------------------+          +---------------------+
| plan_approval        |          |                     |
| submit: {plan:"..."}| -------> | reviews plan text   |
+---------------------+          | approve/reject?     |
                                 +---------------------+
                                         |
+---------------------+          +-------v-------------+
| plan_approval_resp   | <------- | plan_approval       |
| {approve: true}      |          | review: {req_id,    |
+---------------------+          |   approve: true}     |
                                 +---------------------+
```

---

## 🔑 关键设计

### 1. Request 追踪器（第 33-37 行）

```python
# 用 request_id 关联请求和响应
shutdown_requests = {}  # request_id -> {"target": name, "status": "pending"}
plan_requests = {}      # request_id -> {"from": name, "status": "pending"}
_tracker_lock = threading.Lock()  # 线程安全
```

**数据结构：**
```python
shutdown_requests = {
    "abc123": {
        "target": "alice",
        "status": "pending",  # pending → approved | rejected
        "timestamp": 1773194400
    }
}
```

### 2. 关闭请求（第 158-180 行）

```python
def request_shutdown(requester: str, target: str) -> str:
    """Lead 请求关闭某个队友"""
    request_id = str(uuid.uuid4())[:8]
    
    # 记录请求
    with _tracker_lock:
        shutdown_requests[request_id] = {
            "target": target,
            "status": "pending",
            "timestamp": time.time()
        }
    
    # 发送关闭请求到目标队友的收件箱
    msg = {
        "type": "shutdown_request",
        "request_id": request_id,
        "requester": requester,
        "timestamp": time.time()
    }
    BUS.send(requester, target, json.dumps(msg))
    
    return f"Shutdown requested: {request_id} -> {target}"
```

**关键设计：**
- 生成唯一 `request_id`
- 记录请求状态（pending）
- 通过 JSONL 信箱发送

### 3. 关闭响应（第 182-205 行）

```python
def respond_to_shutdown(responder: str, request_id: str, approve: bool) -> str:
    """队友响应关闭请求"""
    with _tracker_lock:
        req = shutdown_requests.get(request_id)
        if not req:
            return f"Error: Unknown request {request_id}"
        
        # 更新状态
        req["status"] = "approved" if approve else "rejected"
        req["responder"] = responder
    
    # 发送响应回 Lead
    msg = {
        "type": "shutdown_response",
        "request_id": request_id,
        "approve": approve,
        "responder": responder
    }
    BUS.send(responder, req["target"], json.dumps(msg))
    
    return f"Shutdown {'approved' if approve else 'rejected'}: {request_id}"
```

**关键设计：**
- 通过 `request_id` 查找原请求
- 更新状态（approved / rejected）
- 发送响应回 Lead

### 4. 队友处理关闭请求（第 230-250 行）

```python
def teammate_loop(name: str, role: str, team: str):
    messages = []
    
    while True:
        # 检查收件箱
        inbox = BUS.read_inbox(name)
        
        for msg in inbox:
            if msg["type"] == "shutdown_request":
                # 队友决定是否批准关闭
                request_id = msg["request_id"]
                requester = msg["requester"]
                
                # 自动批准（简单实现）
                approve = True
                
                # 发送响应
                respond_to_shutdown(name, request_id, approve)
                
                if approve:
                    # 优雅关闭
                    print(f"[{name}] shutting down...")
                    return  # 退出循环，线程结束
        
        # ... 正常工作循环 ...
```

**关键设计：**
- 队友自己决定是否批准
- 批准后退出循环（线程结束）
- 优雅关闭（不是强制杀死）

### 5. 计划审批（第 207-228 行）

```python
def submit_plan(submitter: str, plan_text: str) -> str:
    """队友提交计划给 Lead 审批"""
    request_id = str(uuid.uuid4())[:8]
    
    with _tracker_lock:
        plan_requests[request_id] = {
            "from": submitter,
            "status": "pending",
            "plan": plan_text
        }
    
    # 发送计划给 Lead
    msg = {
        "type": "plan_approval",
        "request_id": request_id,
        "plan": plan_text,
        "submitter": submitter
    }
    BUS.send(submitter, "lead", json.dumps(msg))
    
    return f"Plan submitted: {request_id}"


def review_plan(reviewer: str, request_id: str, approve: bool, 
                feedback: str = "") -> str:
    """Lead 审批计划"""
    with _tracker_lock:
        req = plan_requests.get(request_id)
        if not req:
            return f"Error: Unknown request {request_id}"
        
        req["status"] = "approved" if approve else "rejected"
        req["feedback"] = feedback
    
    # 发送审批结果
    msg = {
        "type": "plan_approval_response",
        "request_id": request_id,
        "approve": approve,
        "feedback": feedback
    }
    BUS.send(reviewer, req["from"], json.dumps(msg))
    
    return f"Plan {'approved' if approve else 'rejected'}: {feedback}"
```

---

## 💡 学习要点

### 1. 理解 Request-Response 关联

**问题：** 异步通信中，如何知道响应对应哪个请求？

**解决：request_id 模式**
```
请求：{request_id: "abc", type: "shutdown_request", ...}
          ↓
响应：{request_id: "abc", type: "shutdown_response", ...}
          ↑
     同一个 ID
```

**好处：**
- 支持多个并发请求
- 请求和响应可以乱序
- 易于调试和审计

### 2. 理解状态机

**关闭协议状态机：**
```
pending ----[approve]----> approved
   |
   +----[reject]---------> rejected
```

**计划审批状态机：**
```
pending ----[approve]----> approved
   |
   +----[reject]---------> rejected
```

**为什么用状态机？**
- 明确的状态转换
- 防止非法操作（如重复审批）
- 易于追踪进度

### 3. 理解优雅关闭

**强制关闭（不好）：**
```python
thread.stop()  # 没有这样的方法
# 或者设置标志，但线程可能不检查
```

**优雅关闭（好）：**
```python
# 1. 发送关闭请求
request_shutdown("lead", "alice")

# 2. 队友收到请求，决定批准
respond_to_shutdown("alice", request_id, approve=True)

# 3. 队友完成当前工作，退出循环
return  # 线程自然结束
```

**好处：**
- 队友可以保存状态
- 可以完成正在进行的工作
- 避免数据损坏

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s10 | OpenClaw |
|------|----------------------|----------|
| **关闭机制** | request/response 协议 | 手动停止服务 |
| **计划审批** | 显式协议 | 无（依赖 Agent 自觉） |
| **请求追踪** | 内存字典 + request_id | 无 |
| **状态机** | pending/approved/rejected | 无 |
| **通信方式** | JSONL 文件 | Feishu 消息 |

**OpenClaw 的差异：**
- OpenClaw 没有显式的关闭协议
- OpenClaw 的 Agent 是常驻服务（不关闭）
- OpenClaw 没有计划审批机制

**可以借鉴的点：**
- 添加 Agent 关闭协议
- 实现任务计划审批
- 用 request_id 追踪异步请求

---

## 📝 练习题

1. **添加超时机制**：请求超过 60 秒无响应自动拒绝
2. **实现强制关闭**：Lead 可以强制关闭不响应的队友
3. **添加计划模板**：预定义计划格式（如"探索型"、"执行型"）
4. **对比 OpenClaw**：我们的 A2A 协作有没有类似的协议？

---

## 🔗 下一步

- **s11 Autonomous Agents** - 自主 Agent（结合关闭协议 + 任务认领）
- **OpenClaw session-chain-manager** - 对比 session 交接协议
- **分布式系统协议** - 学习更多 request-response 模式

---

*参考：分布式系统中的 Request-Response 模式和状态机设计*
