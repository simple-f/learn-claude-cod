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
- `blocks` - 哪些任务依赖我（后置任务）
- `owner` - 负责人（s11 用到）

### 2. 更新任务状态

```python
def update(self, task_id: int, status: str = None,
           add_blocked_by: list = None, add_blocks: list = None) -> str:
    task = self._load(task_id)
    
    if status:
        task["status"] = status
        # 关键：完成任务时，从所有其他任务的 blockedBy 中移除
        if status == "completed":
            self._clear_dependency(task_id)
    
    if add_blocked_by:
        task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
    
    if add_blocks:
        task["blocks"] = list(set(task["blocks"] + add_blocks))
        # 双向更新：同时更新被阻塞任务的 blockedBy
        for blocked_id in add_blocks:
            blocked = self._load(blocked_id)
            if task_id not in blocked["blockedBy"]:
                blocked["blockedBy"].append(task_id)
                self._save(blocked)
    
    self._save(task)
```

**关键逻辑：**
- 完成任务 → 自动解除其他任务的阻塞
- 添加依赖 → 双向更新（A blocks B → B blockedBy A）

### 3. 清除依赖（第 86-91 行）

```python
def _clear_dependency(self, completed_id: int):
    """Remove completed_id from all other tasks' blockedBy lists."""
    for f in self.dir.glob("task_*.json"):
        task = json.loads(f.read_text())
        if completed_id in task.get("blockedBy", []):
            task["blockedBy"].remove(completed_id)
            self._save(task)
```

**为什么重要？**
- 任务 1 完成后，任务 2 自动解锁
- 不需要手动管理依赖关系
- Agent 可以看到哪些任务现在可以做了

### 4. 列出所有任务（第 93-104 行）

```python
def list_all(self) -> str:
    tasks = []
    for f in sorted(self.dir.glob("task_*.json")):
        tasks.append(json.loads(f.read_text()))
    
    lines = []
    for t in tasks:
        marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
        blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
        lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
    
    return "\n".join(tasks)
```

**输出格式：**
```
[ ] #1: 设计数据库 schema
[>] #2: 实现用户认证 (blocked by: [1])
[ ] #3: 创建登录页面 (blocked by: [2])
[x] #4: 项目初始化
```

---

## 💡 学习要点

### 1. 理解外部状态

**对话内状态（易失）：**
```python
messages = [...]  # 可能被压缩/丢失
```

**对话外状态（持久）：**
```python
.tasks/task_1.json  # 永远存在，除非删除
```

**好处：**
- 对话压缩不丢失任务
- 重启后任务还在
- 多 Agent 共享任务板

### 2. 理解依赖管理

**前置依赖（blockedBy）：**
```json
{
  "id": 2,
  "subject": "实现用户认证",
  "blockedBy": [1]  // 任务 1 完成后才能做
}
```

**后置依赖（blocks）：**
```json
{
  "id": 1,
  "subject": "设计数据库 schema",
  "blocks": [2, 3]  // 任务 2 和 3 要等我完成
}
```

**双向更新的好处：**
- 从任务 1 看：知道谁在等我
- 从任务 2 看：知道我在等谁

### 3. 理解状态机

```
pending → in_progress → completed
   ↑
   └── 可以来回切换
```

**状态转换规则：**
- pending → in_progress：开始做
- in_progress → completed：完成
- in_progress → pending：暂停
- completed → in_progress：重新打开

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s07 | OpenClaw |
|------|----------------------|----------|
| **任务存储** | `.tasks/` JSON 文件 | `memory/` + `HEARTBEAT.md` |
| **依赖管理** | blockedBy/blocks 图 | 无（任务独立） |
| **任务分配** | owner 字段（s11 用） | A2A 路由（@mention） |
| **状态追踪** | pending/in_progress/completed | 无明确状态 |
| **自动解锁** | 完成后自动解除阻塞 | 无 |

**OpenClaw 可以借鉴的点：**
- 添加任务依赖管理
- 用 JSON 文件存储任务（更结构化）
- 自动解锁机制

---

## 📝 练习题

1. **添加任务优先级**：`priority` 字段（high/medium/low）
2. **添加任务标签**：`tags` 字段（如 `["backend", "urgent"]`）
3. **添加截止日期**：`due_date` 字段，超期提醒
4. **实现任务看板**：按状态分组显示任务

---

## 🔗 下一步

- **s08 Background Tasks** - 后台任务（并行执行）
- **s11 Autonomous Agents** - 自主认领任务
- **OpenClaw HEARTBEAT.md** - 对比我们的任务管理方式

---

*参考：OpenClaw 的 HEARTBEAT.md 和 memory/ 目录*
