# s01 Agent Loop - 学习笔记

## 📌 核心概念

**Agent Loop 是什么？**

这是所有 AI Agent 的**最核心模式**——一个无限循环，不断：
1. 问 LLM："该做什么？"
2. LLM 说："调用工具 X"
3. 执行工具
4. 把结果告诉 LLM
5. 重复，直到 LLM 说"完成了"

```
┌──────────┐    ┌─────┐    ┌────────┐
│  User    │ →  │ LLM │ →  │  Tool  │
│  Query   │    │     │    │ Execute│
└──────────┘    └──┬──┘    └───┬────┘
                   ↑           │
                   │  Result   │
                   └───────────┘
                 (循环继续)
```

## 🔑 关键代码段

### 1. 核心循环（第 60-77 行）

```python
def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        
        if response.stop_reason != "tool_use":
            return  # 模型说完成了
        
        # 执行工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block.input["command"])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })
        
        messages.append({"role": "user", "content": results})  # 关键！
```

**为什么要把工具结果加回消息？**

因为 LLM 是**无状态**的，它不知道工具执行的结果。你必须把结果"喂"回去，它才能：
- 判断任务是否完成
- 决定下一步做什么
- 根据输出调整策略

这就是 **ReAct 模式**（Reason + Act）的精髓。

### 2. 工具定义（第 26-35 行）

```python
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]
```

**这是 Function Calling 的标准格式**，告诉 LLM：
- 有什么工具可用
- 工具是干什么的
- 需要什么参数

### 3. 安全检查（第 40-50 行）

```python
def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
```

**生产环境必须做安全检查**，否则 LLM 可能执行危险命令。

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s01 | OpenClaw |
|------|----------------------|----------|
| **循环位置** | 单次会话内 | 常驻进程 + 心跳 |
| **工具定义** | 硬编码 JSON | Skills 系统（38+ 内置） |
| **消息历史** | 内存列表 | 持久化到 session 文件 |
| **安全检查** | 简单黑名单 | 多层护栏 + 权限控制 |
| **人格** | 无 | SOUL.md（毒舌 PM） |
| **记忆** | 无 | MEMORY.md + 日常笔记 |

**OpenClaw 多了什么？**
- 常驻服务（不用每次启动）
- 飞书集成（IM 通道）
- 多 Agent 协作（A2A 路由）
- 定时任务（Cron + Heartbeat）
- 人格和记忆系统

## 💡 学习要点

1. **理解循环**：while + tool_use 判断
2. **理解状态**：messages 列表就是"记忆"
3. **理解工具**：LLM 通过工具改变世界
4. **理解反馈**：工具结果必须喂回 LLM

---

## 🔬 深度技术解析

### 1. 为什么要把工具结果加回 messages？

**详细原理：**

LLM 是**无状态**的。这意味着它每次调用都是"全新的"，不知道之前发生了什么。

```
错误示范（不加结果）：
第 1 次调用：
你："执行命令 ls"
LLM: {"tool_use": "bash", "command": "ls"}

第 2 次调用（如果不加结果）：
你："执行命令 ls"
LLM: {"tool_use": "bash", "command": "ls"}  # 完全一样！
```

**正确的流程：**

```
第 1 次调用：
你："执行命令 ls"
LLM: {"tool_use": "bash", "command": "ls"}

你："工具执行结果是：file1.txt, file2.txt"  ← 关键！
LLM: "好的，目录中有两个文件"  # 现在它知道了
```

**这就是 ReAct 模式的核心：**

```
Reason（推理）→ Act（行动）→ Observe（观察）→ Reason（推理）→ ...
```

每次循环都要把观察结果告诉 LLM，它才能判断任务是否完成、决定下一步做什么。

**类比人类思考：**

```
你："我要写一个 Python 脚本"
   ↓
打开编辑器（行动）
   ↓
看到空白屏幕（观察）← 如果没有这一步，你就不知道屏幕是空白的
   ↓
"好的，现在开始写代码"（新的推理）
```

**常见错误：**

```python
# ❌ 错误：执行了工具但不告诉 LLM
for block in response.content:
    if block.type == "tool_use":
        run_bash(block.input["command"])
        # 忘记把结果加回去

# ✅ 正确：执行后必须反馈
for block in response.content:
    if block.type == "tool_use":
        result = run_bash(block.input["command"])
        results.append({"type": "tool_result", "content": result})

messages.append({"role": "user", "content": results})
```

---

### 2. stop_reason 状态机原理

**为什么 `stop_reason != "tool_use"` 就返回？**

Anthropic API 的 `stop_reason` 有几种可能的值：

| stop_reason | 含义 | 应该怎么做 |
|-------------|------|------------|
| `tool_use` | LLM 想调用工具 | 执行工具，继续循环 |
| `end_turn` | LLM 说完了 | 返回结果，结束 |
| `max_tokens` | 达到 token 限制 | 截断或继续 |
| `stop_sequence` | 遇到停止序列 | 结束 |

**状态机图示：**

```
         ┌──────────────┐
         │  开始循环    │
         └──────┬───────┘
                │
         ┌──────▼───────┐
         │ 调用 LLM     │
         └──────┬───────┘
                │
         ┌──────▼───────┐
    ┌────│ stop_reason? │────┐
    │    └──────┬───────┘    │
    │           │            │
tool_use     end_turn     max_tokens
    │           │            │
    │           ▼            ▼
执行工具    返回结果     继续或截断
    │
    ▼
继续循环
```

**为什么这样设计？**

这是**最小权限原则**：
- LLM 默认是"助手"，不是"执行者"
- 它必须明确说"我要调用工具"
- 它说"完成了"就停止

---

### 3. max_tokens 设置的最佳实践

**为什么 max_tokens 设为 8000？**

`max_tokens` 是 LLM 单次响应的**最大输出长度**。

**计算方式：**

```
1 个 token ≈ 4 个英文字符 ≈ 2 个汉字

8000 tokens ≈ 32000 英文字符 ≈ 16000 汉字
```

**为什么是 8000？**

这是 Claude 3.5 Sonnet 的**推荐值**：

| 模型 | 最大输出 tokens | 推荐 max_tokens |
|------|----------------|-----------------|
| Claude 3 Haiku | 4096 | 4000 |
| Claude 3 Sonnet | 4096 | 4000 |
| Claude 3 Opus | 4096 | 4000 |
| Claude 3.5 Sonnet | 8192 | 8000 |

**设置太小的问题：**

```python
# ❌ 太小：可能被截断
max_tokens=1000

# LLM 正在写代码，写到一半：
# "def calculate_sum(numbers):
#     total = 0
#     for n in numbers:
#         total += ... [截断]"
```

**设置太大的问题：**

```python
# ❌ 太大：浪费钱 + 时间长
max_tokens=100000

# LLM 可能啰嗦半天，你还要为多余的 tokens 付费
```

**最佳实践：**

- **简单任务**（问答）：1000-2000
- **中等任务**（代码生成）：4000-8000
- **复杂任务**（长文档）：8000+

## 📝 练习题

1. 修改 `run_bash`，添加命令白名单模式
2. 添加一个新工具（比如 `read_file`）
3. 实现简单的错误重试机制
4. 对比 OpenClaw 的 `sessions_spawn`，思考差异

## 🔗 下一步

学完 s01 后，继续：
- **s02 Tool Use** - 更复杂的工具调用
- **s04 Subagent** - 如何派生子任务（对标 OpenClaw 的 `sessions_spawn`）
- **s09 Agent Teams** - 多 Agent 协作（对标我们的飞书 A2A）
