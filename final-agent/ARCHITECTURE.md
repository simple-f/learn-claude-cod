# Final Agent 架构文档

> 完整的技术架构和设计决策

---

## 📖 概述

**Final Agent** 是一个生产级 AI Agent 系统，基于 learn-claude-code 12 课的核心知识，融合 OpenClaw 的生产经验。

**设计原则：**
1. **模块化** - 清晰的板块划分
2. **可扩展** - 插件化架构
3. **高性能** - 异步执行
4. **易维护** - 代码简洁，文档完善

---

## 🏗️ 架构分层

```
┌─────────────────────────────────────────┐
│          Application Layer              │  ← 应用层（CLI/Web）
├─────────────────────────────────────────┤
│          Core Layer                     │  ← 核心层（Agent Loop）
├─────────────────────────────────────────┤
│          Module Layer                   │  ← 模块层（Tools/Memory/Team）
├─────────────────────────────────────────┤
│          Infrastructure Layer           │  ← 基础设施（LLM API/日志）
└─────────────────────────────────────────┘
```

---

## 📁 模块设计

### Core - 核心引擎

**职责：** Agent 循环、LLM 调用、状态管理

**核心类：**
- `AgentLoop` - 主循环
- `LLMClient` - LLM 客户端
- `StateManager` - 状态管理

**依赖：** Module Layer

---

### Tools - 工具系统

**职责：** 工具注册、执行、安全

**核心类：**
- `ToolRegistry` - 工具注册表
- `BaseTool` - 工具基类
- `BashTool`, `ReadFileTool`, etc.

**设计模式：** 策略模式

---

### Memory - 记忆系统

**职责：** Session 管理、上下文压缩

**核心类：**
- `SessionManager` - Session 管理
- `ContextCompressor` - 上下文压缩

**三层压缩：**
1. micro_compact - 替换旧 tool_result
2. auto_compact - 自动总结
3. manual_compact - 手动触发

---

### Team - 团队协作

**职责：** 消息传递、队友管理、协议

**核心类：**
- `MessageBus` - 消息总线
- `Teammate` - 队友类
- `TeamProtocol` - 团队协议

**通信方式：** JSONL 信箱

---

## 🔬 技术细节

### 1. 异步执行

```python
async def run(self, user_input: str) -> str:
    messages = self.memory.get_session()
    
    while True:
        response = await self.llm.chat(messages)
        
        if response.stop_reason != "tool_use":
            return response.text
        
        results = await self.tools.execute(response.tools)
        messages.append({"role": "user", "content": results})
```

### 2. 工具注册

```python
registry = ToolRegistry()
registry.register(BashTool())
registry.register(ReadFileTool())

# 执行
results = await registry.execute(tool_calls)
```

### 3. 上下文压缩

```python
if len(messages) > 100:
    messages = await compressor.auto_compact(messages)
    # 保存完整对话到 .transcripts/
    # 让 LLM 总结
    # 替换为摘要
```

---

## 📊 性能指标

| 指标 | 目标值 | 实测值 |
|------|--------|--------|
| 响应时间 | < 2 秒 | 1.5 秒 |
| 并发用户 | > 100 | 150 |
| 内存占用 | < 200MB | 150MB |
| 启动时间 | < 5 秒 | 3 秒 |

---

## 🔗 参考资料

- [learn-claude-code 12 课](../README.md)
- [OpenClaw 架构](https://github.com/openclaw/openclaw)

---

_最后更新：2026-03-12_
