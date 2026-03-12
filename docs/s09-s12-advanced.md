# s09-s12 深度技术解析

> 团队协作与隔离机制详解

---

## s09 Agent Teams - 深度解析

### 1. 为什么用 JSONL 信箱？

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

**覆盖场景：**
- 日常工作：message
- 团队通知：broadcast
- 生命周期管理：shutdown_request/response
- 任务协调：plan_approval_response

更多类型会增加复杂度，这 5 种已足够。

---

## s10 Team Protocols - 深度解析

### 1. 为什么需要关闭协议？

**详细原理：**

这是**优雅关闭**的设计，防止数据丢失。

**对比两种方案：**

```python
# ❌ 方案 1：强制关闭
process.kill()

# 问题：
# - 正在执行的任务中断
# - 文件可能损坏
# - 消息丢失

# ✅ 方案 2：优雅关闭
send_shutdown_request()
# 等待队友完成当前任务
# 保存状态
# 确认关闭
```

**关闭流程：**

```
Lead: "可以下班了" (shutdown_request)
  ↓
Alice: "好的，代码保存中..." (working)
  ↓
Alice: "保存完成，可以关闭" (shutdown_response: approved)
  ↓
Lead: 关闭 Alice 的线程
```

---

### 2. 为什么需要计划审批？

**详细原理：**

这是**质量控制**的设计。

**对比两种方案：**

```python
# ❌ 方案 1：直接执行
plan = create_plan()
execute(plan)  # 可能有问题

# ✅ 方案 2：审批后执行
plan = create_plan()
send_for_approval(plan)
# 等待 Lead 批准
if approved:
    execute(plan)
else:
    revise(plan)
```

**好处：**
- 防止错误决策
- 统一团队方向
- 知识传递（Lead 可以指导）

---

## s11 Autonomous Agents - 深度解析

### 1. 为什么用空闲轮询？

**详细原理：**

这是**主动式工作**的设计。

**对比两种方案：**

```python
# ❌ 方案 1：被动等待
while True:
    messages = read_inbox()
    if messages:
        process(messages)
    # 无事可做时睡觉

# ✅ 方案 2：主动轮询
while True:
    messages = read_inbox()
    if messages:
        process(messages)
    else:
        # 主动找活干
        tasks = scan_task_board()
        available = [t for t in tasks if t.status == "available"]
        if available:
            claim(available[0])
```

**好处：**
- 减少等待时间
- 提高团队效率
- 自主性强

---

### 2. 为什么用任务看板？

**详细原理：**

这是**可视化协作**的设计。

**看板状态：**

```
+------------+------------+------------+------------+
| 待处理     | 进行中      | 审查中      | 已完成      |
+------------+------------+------------+------------+
| 任务 A     | 任务 B     | 任务 C     | 任务 D     |
| 任务 E     |            |            | 任务 F     |
+------------+------------+------------+------------+
```

**好处：**
- 一目了然
- 自主认领
- 避免冲突

---

## s12 Worktree Isolation - 深度解析

### 1. 为什么用 worktree 隔离？

**详细原理：**

这是**物理隔离**的设计，防止任务间干扰。

**对比多种方案：**

```python
# ❌ 方案 1：无隔离
# 所有任务在同一个目录
# 问题：文件冲突、git 状态混乱

# ❌ 方案 2：分支隔离
git checkout -b task-1
# 问题：切换分支耗时、容易忘

# ✅ 方案 3：worktree 隔离
git worktree add .worktrees/task-1 -b task-1
# 好处：
# - 并行工作（不切换）
# - 物理隔离（目录分开）
# - 易于清理
```

**实际效果：**

```
项目根目录/
  .worktrees/
    task-1/      # 任务 1 的工作目录
    task-2/      # 任务 2 的工作目录
  .tasks/
    task-1.json  # 任务 1 的元数据
    task-2.json  # 任务 2 的元数据
```

---

### 2. 为什么任务与 worktree 绑定？

**详细原理：**

这是**控制平面与执行平面分离**的设计。

**架构图：**

```
控制平面（.tasks/）          执行平面（.worktrees/）
+------------------+         +------------------+
| task_1.json      | ------> | task-1/          |
| { status: "...", |         |  src/            |
|   worktree: "x" }|         |  tests/          |
+------------------+         +------------------+
```

**好处：**
- 任务状态独立于代码
- 可以查询所有任务进度
- 易于清理（删除 worktree + 更新任务状态）

---

### 3. 为什么用 Git worktree？

**详细原理：**

这是**官方支持的并行开发**工具。

**对比多种方案：**

```python
# ❌ 方案 1：复制目录
cp -r project task-1
# 问题：
# - 占用磁盘空间
# - git 历史不共享
# - 难以合并

# ❌ 方案 2：stash
git stash push
git checkout -b task-1
# 问题：
# - 只能串行
# - 容易忘记 stash

# ✅ 方案 3：worktree
git worktree add .worktrees/task-1 -b task-1
# 好处：
# - 共享.git 目录（节省空间）
# - 共享历史
# - 支持并行
# - 官方支持
```

---

## 总结

| 课程 | 核心设计 | 原理 |
|------|----------|------|
| s09 | JSONL 信箱 | 持久化 + 解耦 |
| s10 | 关闭协议 | 优雅关闭 + 质量控制 |
| s11 | 空闲轮询 | 主动式工作 |
| s12 | worktree 隔离 | 物理隔离 + 并行开发 |

---

_最后更新：2026-03-12_
