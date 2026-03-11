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
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)[:50000]})
        sub_messages.append({"role": "user", "content": results})
    
    # 3. 只返回最终文本摘要（子 Agent 的完整上下文被丢弃）
    return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"
```

**关键设计：**
- `sub_messages = []` - 全新对话历史
- `for _ in range(30)` - 安全限制（防止无限循环）
- 只返回 `response.content` 中的文本部分
- 子 Agent 的完整对话历史在函数结束后被丢弃

### 2. 工具权限分离（第 81-92 行）

```python
# 子 Agent 的工具（没有 task 工具，不能递归派生）
CHILD_TOOLS = [
    {"name": "bash", ...},
    {"name": "read_file", ...},
    {"name": "write_file", ...},
    {"name": "edit_file", ...},
]

# 父 Agent 的工具（包含 task 工具）
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task", "description": "Spawn a subagent with fresh context...",
     "input_schema": {"type": "object", 
         "properties": {"prompt": {"type": "string"}, 
                       "description": {"type": "string"}}, 
         "required": ["prompt"]}},
]
```

**权限设计：**
- 子 Agent 没有 `task` 工具（不能递归派生子 Agent）
- 防止无限嵌套（父→子→孙→...）
- 父 Agent 可以派生多个子 Agent 并行工作

### 3. 父 Agent 循环（第 95-115 行）

```python
def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=PARENT_TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        
        results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "task":
                    # 派生子 Agent
                    desc = block.input.get("description", "subtask")
                    print(f"> task ({desc}): {block.input['prompt'][:80]}")
                    output = run_subagent(block.input["prompt"])
                else:
                    # 执行普通工具
                    handler = TOOL_HANDLERS.get(block.name)
                    output = handler(**block.input)
                print(f"  {str(output)[:200]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        messages.append({"role": "user", "content": results})
```

---

## 💡 学习要点

### 1. 理解上下文隔离

**没有子 Agent 的情况：**
```
messages = [
  "用户：分析这个项目",
  "助手：好的，我先看看目录结构",
  "工具结果：dir 输出（1000 行）",
  "助手：现在读取 README",
  "工具结果：README 内容（500 行）",
  "助手：现在读取 package.json",
  "工具结果：package.json 内容",
  ...
  # 上下文越来越长，token 消耗巨大
]
```

**有子 Agent 的情况：**
```
Parent messages = [
  "用户：分析这个项目",
  "助手：我来派生子 Agent 分析",
  "工具结果：子 Agent 总结（100 字）",
  # 上下文保持干净
]

Subagent messages = [
  "用户：分析这个项目",
  "助手：好的，我先看看目录结构",
  "工具结果：dir 输出（1000 行）",
  ...
  # 完整的探索过程，但完成后被丢弃
]
```

### 2. 理解任务委派

**父 Agent 的决策：**
```python
if block.name == "task":
    output = run_subagent(block.input["prompt"])
```

**子 Agent 的执行：**
- 独立探索
- 独立决策
- 独立执行工具
- 只返回总结

**好处：**
- 父 Agent 保持"清醒"（不被细节淹没）
- 子 Agent 专注特定任务
- 可以并行派生多个子 Agent

### 3. 理解安全限制

```python
for _ in range(30):  # 最多 30 轮
```

**为什么限制 30 轮？**
- 防止子 Agent 无限循环
- 控制成本（token 消耗）
- 强制子 Agent 尽快给出总结

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s04 | OpenClaw |
|------|----------------------|----------|
| **子进程** | `run_subagent()` 函数 | `sessions_spawn()` |
| **上下文隔离** | 全新 `messages=[]` | 独立 session |
| **通信方式** | 返回值（字符串） | session 消息传递 |
| **权限控制** | 工具过滤（CHILD_TOOLS） | 运行时隔离 |
| **生命周期** | 同步执行（阻塞） | 异步执行（可后台） |
| **递归限制** | 无 task 工具 | 可配置 |

**OpenClaw 的差异：**
- OpenClaw 的 `sessions_spawn` 是异步的（不阻塞主循环）
- OpenClaw 支持持久化 session（子 Agent 可以长期运行）
- OpenClaw 有 A2A 路由（多 Agent 协作）

**可以借鉴的点：**
- 添加同步子 Agent 模式（简单任务）
- 实现上下文压缩前派生子 Agent
- 工具权限分级（基础工具 vs 高级工具）

---

## 📝 练习题

1. **添加超时机制**：子 Agent 超过 60 秒自动终止
2. **添加进度报告**：子 Agent 定期向父 Agent 汇报进度
3. **实现并行派生**：同时派生 3 个子 Agent 处理不同任务
4. **对比 OpenClaw**：我们的 `sessions_spawn` 和 s04 有什么区别？

---

## 🔗 下一步

- **s09 Agent Teams** - 持久化团队协作（不是用完即弃）
- **OpenClaw sessions_spawn** - 查看 `skills/coding-agent/SKILL.md`
- **s11 Autonomous Agents** - 自主 Agent（自己寻找工作）

---

*参考：OpenClaw 的 sessions_spawn 和 A2A 协作系统*
