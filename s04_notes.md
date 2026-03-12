# s04 Subagent - 学习笔记

## 📌 核心洞察

> **"Process isolation gives context isolation for free."**

这是 s04 最重要的设计思想：**通过进程隔离实现上下文隔离——子 Agent 有全新的对话历史，父 Agent 的上下文保持干净**。

---

## 🏗️ 架构图

```
Parent Agent                     Subagent
+------------------+             +------------------+
| messages=[...]   |             | messages=[]      |  <-- 全新上下文
|                  |  dispatch   |                  |
| tool: task       | ---------->| while tool_use:  |
|   prompt="..."   |            |   call tools     |
|   description="" |            |   append results |
|                  |  summary   |                  |
|   result = "..." | <--------- | return last text |
+------------------+             +------------------+
          |
  Parent context stays clean.
  Subagent context is discarded.
```

---

## 🔑 关键设计

### 1. 子 Agent 函数（第 57-78 行）

```python
def run_subagent(prompt: str) -> str:
    # 1. 创建全新的对话历史（只有用户提示）
    sub_messages = [{"role": "user", "content": prompt}]
    
    # 2. 运行独立的 Agent 循环（最多 30 轮）
    for _ in range(30):
        response = client.messages.create(
            model=MODEL, system=SUBAGENT_SYSTEM, messages=sub_messages,
            tools=CHILD_TOOLS, max_tokens=8000,
        )
        sub_messages.append({"role": "assistant", "content": response.content})
        
        # 如果模型不调用工具，结束
        if response.stop_reason != "tool_use":
            break
        
        # 执行工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = TOOL_HANDLERS[block.name](**block.input)
                results.append({"type": "tool_result", "content": output})
        
        sub_messages.append({"role": "user", "content": results})
    
    # 3. 返回最后一次响应
    return response.content[-1].text
```

### 2. 工具定义（第 18-35 行）

```python
TASK_TOOL = {
    "name": "task",
    "description": "Delegate a self-contained subtask to a subagent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Full context for the subagent. Include all necessary information."
            },
            "description": {
                "type": "string",
                "description": "One-line summary of the task."
            }
        },
        "required": ["prompt", "description"]
    }
}
```

### 3. 系统提示词（第 8-15 行）

```python
SUBAGENT_SYSTEM = """You are a coding assistant.
You have access to bash, read_file, write_file, edit_file.
When the task is complete, respond with the final result.
Do not delegate tasks to other agents."""
```

**关键指令：**
- 可以调用工具
- 完成后返回结果
- **不能再次派生子 Agent**（防止无限递归）

---

## 💡 学习要点

### 1. 理解上下文隔离

子 Agent 的 `messages` 列表是**全新的**，不包含父 Agent 的对话历史。

**好处：**
- 父 Agent 上下文保持干净
- 子 Agent 专注当前任务
- 节省 tokens（不重复传递历史）

### 2. 理解任务分解

```
用户："分析这个项目"
  ↓
Parent: "先看看目录结构"
  ↓
task: "列出当前目录的文件"
  ↓
Subagent: 执行 ls -la → 返回结果
  ↓
Parent: "好的，现在看看 README"
```

### 3. 理解递归限制

**为什么子 Agent 不能再派生子 Agent？**

```python
# SUBAGENT_SYSTEM 明确禁止
"Do not delegate tasks to other agents."
```

**防止无限递归：**

```
Parent → Subagent1 → Subagent2 → Subagent3 → ...
```

如果不限制，可能：
- Token 爆炸
- 任务迷失
- 难以调试

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s04 | OpenClaw |
|------|----------------------|----------|
| **子 Agent 实现** | 独立进程（Claude Code CLI） | `sessions_spawn` API |
| **上下文隔离** | 全新 messages 列表 | 独立 session 文件 |
| **通信方式** | 进程间管道 | A2A 路由器 + 飞书消息 |
| **递归限制** | 系统提示词禁止 | 深度限制（maxDepth=15） |
| **结果返回** | 字符串摘要 | 结构化 Handoff 5 件套 |

**OpenClaw 的改进：**
- 支持多轮 A2A 协作（不仅是一次性派子任务）
- 有深度追踪和循环检测
- 支持异步通知（子任务完成后主动通知）

---

## 🔬 深度技术解析

### 1. 为什么给子 agent 独立的 messages？

**详细原理：**

这是**上下文隔离**的设计，避免"上下文污染"。

**对比两种方案：**

```python
# ❌ 方案 1：共享 messages
sub_messages = parent_messages.copy()  # 继承父 agent 的所有历史

# 问题：
# 1. 子 agent 看到父 agent 的所有对话，可能混淆
# 2. tokens 浪费（很多上下文不相关）
# 3. 子 agent 可能被父 agent 的错误误导

# ✅ 方案 2：独立 messages
sub_messages = [
    {"role": "system", "content": "你是一个专门做 X 的助手"},
    {"role": "user", "content": "请完成这个任务..."}
]

# 好处：
# 1. 干净的上下文
# 2. 专注当前任务
# 3. 节省 tokens
```

**类比人类工作：**

```
老板："帮我写个登录功能"

❌ 共享上下文：
你拿到老板所有的邮件、会议记录、聊天历史
→ 信息过载，不知道从哪开始

✅ 独立上下文：
你拿到一张任务卡片："写登录功能，要求：1. 2. 3."
→ 专注执行
```

**实际代码对比：**

```python
# OpenClaw 的 sessions_spawn（独立上下文）
await sessions_spawn(
    task="实现用户认证模块",
    agent_id="ai2",
    # 只传递必要的上下文
    attachments=[{"name": "requirements.md", "content": "..."}]
)

# 而不是传递整个会话历史
```

---

### 2. 为什么限制 30 轮？

**详细原理：**

这是**防止无限循环**和**控制成本**的双重考虑。

**计算方式：**

```
成本计算：
- 每轮调用 1 次 API
- 每次 API 约 1000-5000 tokens
- 30 轮 ≈ 30 次调用 ≈ $0.03-$0.15

时间计算：
- 每轮约 2-5 秒
- 30 轮 ≈ 60-150 秒 ≈ 1-2 分钟
```

**为什么是 30？**

```
经验值：
- 简单任务：5-10 轮
- 中等任务：10-20 轮
- 复杂任务：20-30 轮
- 超过 30 轮：可能陷入循环或方向错误
```

**如果任务真的需要更多轮怎么办？**

```python
# 方案 1：任务分解
任务 A（30 轮）→ 任务 A1（15 轮）+ 任务 A2（15 轮）

# 方案 2：进度报告
每 10 轮向父 Agent 报告进度，让父 Agent 决定是否继续

# 方案 3：动态限制
if task_complexity == "high":
    max_rounds = 50
else:
    max_rounds = 30
```

---

### 3. 为什么禁止子 Agent 再派子 Agent？

**详细原理：**

这是**防止指数爆炸**的设计。

**如果不禁止：**

```
Parent (1 个)
  ↓
Subagent1 (1 个)
  ↓
Subagent2 (2 个)
  ↓
Subagent3 (4 个)
  ↓
Subagent4 (8 个)
  ...
  ↓
Subagent10 (512 个)  ← 爆炸！
```

**成本计算：**

```
每层 2 个子任务，10 层后：
- API 调用：2^10 = 1024 次
- 成本：1024 × $0.01 = $10.24
- 时间：1024 × 3 秒 = 51 分钟
```

**对比允许递归的系统：**

| 系统 | 递归限制 | 原因 |
|------|----------|------|
| **s04 Subagent** | 禁止 | 防止爆炸 |
| **OpenClaw A2A** | maxDepth=15 | 可控递归 |
| **AutoGen** | 可配置 | 灵活性 |
| **CrewAI** | 可配置 | 灵活性 |

**什么时候可以放宽？**

```python
# 场景：需要多层分解的复杂任务
# 可以改为：
MAX_DEPTH = 3  # 允许最多 3 层

def run_subagent(prompt: str, depth: int = 0):
    if depth >= MAX_DEPTH:
        raise ValueError("Max depth reached")
    
    # 递归调用
    return run_subagent(new_prompt, depth + 1)
```

---

## 📝 练习题

1. **添加进度报告**：子 Agent 每 10 轮向父 Agent 报告
2. **实现动态限制**：根据任务复杂度调整 max_rounds
3. **添加超时机制**：超过 5 分钟自动终止
4. **对比 OpenClaw**：分析 `sessions_spawn` 和 s04 的区别

---

## 🔗 下一步

- **s05 Skill Loading** - 如何动态加载技能（对标 Skills 系统）
- **s07 Task System** - 任务持久化（JSON 文件存储）
- **s09 Agent Teams** - 多 Agent 协作（对标飞书 A2A）

---

*参考：OpenClaw 的 `sessions_spawn` 和 A2A 路由器*
