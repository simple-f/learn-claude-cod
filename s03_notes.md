# s03 TodoWrite - 学习笔记

## 📌 核心概念

**TodoWrite 是什么？**

让 Agent 能够**追踪自己的进度**——通过一个结构化的待办事项列表。

```
用户提问 → LLM 制定计划 → 执行任务 → 更新状态 → 完成
                ↓
          TodoManager 记录进度
```

**为什么需要 Todo？**

- **可见性**：人类可以看到 Agent 的工作进度
- **自我追踪**：Agent 知道自己做了什么、还要做什么
- **防止迷失**：多步骤任务中保持方向

---

## 🔑 关键设计

### 1. TodoManager 类（第 33-72 行）

```python
class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        # 验证：最多 20 项、必须有 text、status 合法
        # 限制：只能有 1 个 in_progress
        
    def render(self) -> str:
        # 渲染格式：
        # [ ] #1: 任务 A
        # [>] #2: 任务 B <- 进行中
        # [x] #3: 任务 C
        # (2/3 completed)
```

**关键验证规则：**
- 最多 20 个待办（防止滥用）
- 必须有 text 字段
- status 只能是 `pending` / `in_progress` / `completed`
- **只能有 1 个任务处于 `in_progress` 状态**

### 2. 工具定义（第 155-175 行）

```python
TOOLS = [
    {"name": "bash", ...},
    {"name": "read_file", ...},
    {"name": "write_file", ...},
    {"name": "edit_file", ...},
    {
        "name": "todo",
        "description": "Update the todo list. Call before starting work and after completing steps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                        },
                        "required": ["text", "status"]
                    }
                }
            },
            "required": ["items"]
        }
    }
]
```

### 3. 系统提示词（第 27-30 行）

```python
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""
```

**关键指令：**
- 开始工作前标记 `in_progress`
- 完成后标记 `completed`
- 优先用工具，不要说空话

---

## 💡 学习要点

### 1. 理解状态管理

TodoManager 是**外部化的状态**——它不在 LLM 的对话历史中，而是独立的 Python 对象。

**好处：**
- 不占用 context tokens
- 可以随时查询和修改
- 人类可以看到进度

### 2. 理解验证逻辑

```python
if in_progress_count > 1:
    raise ValueError("Only one task can be in_progress at a time")
```

**为什么限制只能有 1 个进行中？**
- 强制 Agent 专注
- 避免并行混乱
- 符合单线程工作模式

### 3. 理解渲染格式

```
[>] #2: 修复登录 bug
      ↑
   视觉提示：这个在做
```

**设计原则：**
- 一眼看出进度
- ID 方便引用
- 完成度统计（2/3 completed）

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s03 | OpenClaw |
|------|----------------------|----------|
| **任务追踪** | TodoManager 内存对象 | HEARTBEAT.md + memory/ 文件 |
| **状态可见性** | 渲染为文本 | 会话状态 + 进展报告 |
| **验证规则** | 代码硬编码 | 无（依赖 Agent 自觉） |
| **任务粒度** | 单 Agent 多步骤 | 多 Agent 协作任务 |

**OpenClaw 可以改进的点：**
- 添加类似 Todo 的结构化任务追踪
- 在会话状态中显示当前任务进度
- 限制并发任务数量（避免分散）

---

## 📝 练习题

1. **添加优先级字段**：给 todo 添加 `priority`（high/medium/low）
2. **添加子任务**：支持嵌套 todo（parent_id 字段）
3. **添加截止日期**：`due_date` 字段，超期提醒
4. **对比 OpenClaw**：我们的 HEARTBEAT.md 和 Todo 有什么区别？

---

## 🔗 下一步

- **s04 Subagent** - 如何派生子任务（对标 `sessions_spawn`）
- **s07 Task System** - 任务持久化（JSON 文件存储）
- **s11 Autonomous Agents** - 自主任务认领

---

*参考：OpenClaw 的 HEARTBEAT.md 和 memory/ 目录结构*
