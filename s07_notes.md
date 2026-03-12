# s07 Task System - 学习笔记

## 📌 核心洞察

> **"State that survives compression -- because it's outside the conversation."**

这是 s07 最重要的设计思想：**任务状态存储在对话之外，所以即使对话被压缩，任务也不会丢失**。

---

## 🏗️ 任务持久化架构

### 目录结构

```
.tasks/
  task_1.json  {"id":1, "subject":"...", "status":"completed", ...}
  task_2.json  {"id":2, "blockedBy":[1], "status":"pending", ...}
  task_3.json  {"id":3, "blockedBy":[2], "blocks":[], ...}
```

### 依赖关系图

```
+----------+     +----------+     +----------+
| task 1   | --> | task 2   | --> | task 3   |
| complete |     | blocked  |     | blocked  |
+----------+     +----------+     +----------+
     |                ^
     +--- 完成后从 task 2 的 blockedBy 中移除
```

---

## 🔑 TaskManager 类（第 33-104 行）

### 1. 创建任务

```python
def create(self, subject: str, description: str = "") -> str:
    task = {
        "id": self._next_id, 
        "subject": subject, 
        "description": description,
        "status": "pending", 
        "blockedBy": [], 
        "blocks": [], 
        "owner": "",
    }
    self._save(task)
    self._next_id += 1
    return json.dumps(task, indent=2)
```

**任务字段：**
- `id` - 自动递增
- `subject` - 简短标题
- `description` - 详细描述
- `status` - pending / in_progress / completed
- `blockedBy` - 依赖哪些任务（前置任务）
- `blocks` - 阻塞哪些任务（后置任务）
- `owner` - 负责人（可选）

### 2. 完成任务

```python
def complete(self, task_id: int) -> str:
    task = self._load(task_id)
    task["status"] = "completed"
    
    # 解锁依赖此任务的任务
    for other in self._all_tasks():
        if task_id in other.get("blockedBy", []):
            other["blockedBy"].remove(task_id)
            self._save(other)
    
    self._save(task)
    return json.dumps(task, indent=2)
```

### 3. 列出任务

```python
def list(self, status_filter: str = "") -> str:
    tasks = self._all_tasks()
    if status_filter:
        tasks = [t for t in tasks if t["status"] == status_filter]
    return json.dumps(tasks, indent=2)
```

---

## 💡 学习要点

### 1. 理解持久化价值

**对比两种方案：**

```python
# ❌ 方案 1：任务在对话历史中
messages = [
    {"role": "user", "content": "创建任务：写登录功能"},
    {"role": "assistant", "content": "好的，任务已创建"},
    {"role": "user", "content": "创建任务：写注册功能"},
    {"role": "assistant", "content": "好的，任务已创建"},
    # ... 随着对话压缩，这些信息可能丢失
]

# 问题：
# - 对话压缩后，任务信息丢失
# - 无法跨会话追踪
# - 难以查询和过滤

# ✅ 方案 2：任务在独立文件中
.tasks/
  task_1.json  {"subject": "写登录功能", "status": "pending"}
  task_2.json  {"subject": "写注册功能", "status": "pending"}

# 好处：
# - 对话压缩不影响任务
# - 跨会话追踪
# - 易于查询和过滤
```

### 2. 理解依赖管理

```
任务依赖关系：
task_1 (完成) → task_2 (等待) → task_3 (等待)

完成 task_1 后：
- task_2 的 blockedBy 移除 task_1
- task_2 变为可执行状态
- task_3 仍然等待 task_2
```

### 3. 理解任务状态

| 状态 | 含义 | 何时使用 |
|------|------|----------|
| `pending` | 等待中 | 刚创建或有依赖未完成 |
| `in_progress` | 进行中 | 开始执行任务 |
| `completed` | 已完成 | 任务完成 |

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s07 | OpenClaw |
|------|----------------------|----------|
| **存储方式** | JSON 文件 | memory/ Markdown 文件 |
| **任务格式** | 结构化 JSON | 自由文本 + frontmatter |
| **依赖管理** | blockedBy/blocks | 无（隐式依赖） |
| **查询方式** | 代码 API | 文件搜索 |
| **跨会话** | ✅ 支持 | ✅ 支持 |

**OpenClaw 可以改进的点：**
- 添加结构化任务追踪
- 实现任务依赖管理
- 提供任务查询 API

---

## 🔬 深度技术解析

### 1. 为什么任务要存储在对话之外？

**详细原理：**

这是**状态与上下文分离**的设计。

**对比分析：**

```
问题：对话会被压缩

场景：
1. Agent 创建 3 个任务
2. 执行任务 1
3. 对话压缩（丢失任务信息）
4. Agent 忘记还有任务 2 和 3

结果：任务丢失
```

**持久化的好处：**

```python
# ✅ 方案 2：独立存储
.tasks/
  task_1.json  # 即使对话压缩，文件还在
  task_2.json
  task_3.json

# 好处：
# - 对话压缩不影响任务
# - 跨会话追踪
# - 易于查询和过滤
# - 支持依赖管理
```

**类比人类工作：**

```
❌ 只记在脑子里：
- 容易忘记
- 无法分享
- 难以追踪

✅ 写在任务列表上：
- 不会忘记
- 可以分享
- 易于追踪
```

---

### 2. 为什么用 JSON 而不是数据库？

**对比多种方案：**

```python
# ❌ 方案 1：SQLite 数据库
# 好处：查询快、支持复杂操作
# 问题：
# - 需要额外依赖
# - 二进制文件，不易读
# - 难以版本控制

# ❌ 方案 2：CSV 文件
# 好处：简单、易读
# 问题：
# - 不支持嵌套结构
# - 难以表示依赖关系

# ✅ 方案 3：JSON 文件
# 好处：
# - 无需额外依赖
# - 人类可读
# - 支持嵌套结构
# - 易于版本控制
# - 每个任务独立文件（便于并发）
```

**实际效果：**

```json
// task_2.json
{
  "id": 2,
  "subject": "写注册功能",
  "blockedBy": [1],  // 依赖任务 1
  "blocks": [3],     // 阻塞任务 3
  "status": "pending"
}
```

---

### 3. 依赖管理原理

**详细原理：**

这是**有向无环图（DAG）**的简化实现。

**依赖关系：**

```
task_1 → task_2 → task_3
   ↓
task_4
```

**数据结构：**

```python
# 每个任务记录：
{
  "id": 2,
  "blockedBy": [1],  # 前置任务
  "blocks": [3],     # 后置任务
}
```

**解锁逻辑：**

```python
def complete(self, task_id):
    # 完成任务
    task["status"] = "completed"
    
    # 解锁依赖此任务的任务
    for other in all_tasks:
        if task_id in other["blockedBy"]:
            other["blockedBy"].remove(task_id)
```

**检测循环依赖：**

```python
def has_cycle(task_id, visited=set()):
    if task_id in visited:
        return True  # 发现循环
    visited.add(task_id)
    for dep in task["blockedBy"]:
        if has_cycle(dep, visited):
            return True
    return False
```

---

## 📝 练习题

1. **添加任务优先级**：high/medium/low
2. **实现任务标签**：支持标签过滤
3. **添加截止日期**：超期提醒
4. **对比 OpenClaw**：设计一个任务管理系统

---

## 🔗 下一步

- **s08 Background Tasks** - 后台任务（异步执行）
- **s09 Agent Teams** - 多 Agent 协作
- **s11 Autonomous Agents** - 自主任务认领

---

*参考：OpenClaw 的 memory/ 目录和 HEARTBEAT.md*
