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
