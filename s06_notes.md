# s06 Context Compact - 学习笔记

## 📌 核心洞察

> **"The agent can forget strategically and keep working forever."**

这是 s06 最重要的设计思想：**通过战略性遗忘，让 Agent 可以永远工作下去**。

---

## 🏗️ 三层压缩管道

```
每个回合：
+------------------+
| 工具调用结果     |
+------------------+
        ↓
[Layer 1: micro_compact]  ← 静默执行，每回合都运行
  替换超过 3 个之前的 tool_result
  为 "[Previous: used {tool_name}]"
        ↓
[检查：tokens > 50000?]
   |               |
   no              yes
   |               |
   ↓               ↓
继续       [Layer 2: auto_compact]
            保存完整对话到 .transcripts/
            让 LLM 总结对话
            替换所有消息为 [summary]
                  |
                  ↓
          [Layer 3: compact 工具]
            Model 调用 compact → 立即总结
            和 auto 一样，但手动触发
```

---

## 🔑 关键代码

### Layer 1: micro_compact（第 37-63 行）

```python
def micro_compact(messages: list) -> list:
    # 收集所有 tool_result
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))
    
    # 只保留最近 3 个，其他的替换为占位符
    if len(tool_results) <= KEEP_RECENT:
        return messages
    
    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        tool_name = tool_name_map.get(tool_id, "unknown")
        result["content"] = f"[Previous: used {tool_name}]"
    
    return messages
```

**压缩策略：**
- 保留最近 3 个工具结果（保持上下文连贯）
- 更早的结果替换为一行占位符
- **不改变消息结构**（LLM 仍然能看到历史）

### Layer 2: auto_compact（第 66-90 行）

```python
def auto_compact(messages: list) -> list:
    # 1. 保存到磁盘
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    
    # 2. 让 LLM 总结
    conversation_text = json.dumps(messages, default=str)[:80000]
    response = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content": 
            "Summarize this conversation for continuity. Include: "
            "1) What was accomplished, 2) Current state, 3) Key decisions made."}],
        max_tokens=2000,
    )
    summary = response.content[0].text
    
    # 3. 替换所有消息为总结
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
    ]
```

**压缩策略：**
- 完整对话保存到 `.transcripts/` 目录
- LLM 生成 2000 tokens 以内的总结
- **只保留 2 条消息**（总结 + 确认）

### Token 估算（第 30-33 行）

```python
def estimate_tokens(messages: list) -> int:
    """粗略估算：~4 字符/token"""
    return len(str(messages)) // 4
```

**阈值设置：**
```python
THRESHOLD = 50000  # 50k tokens 触发自动压缩
```

---

## 💡 学习要点

### 1. 理解压缩时机

**micro_compact（每回合）：**
- 轻量级（不改变消息数量）
- 只是缩短长输出
- 类似"截断"而非"总结"

**auto_compact（超过阈值）：**
- 重量级（改变消息结构）
- 真正减少消息数量
- 丢失细节但保留要点

### 2. 理解持久化策略

```
.transcripts/
  transcript_1773194400.jsonl  # 完整对话备份
  transcript_1773195200.jsonl
  ...
```

**为什么保存完整对话？**
- 压缩是不可逆的（丢失细节）
- 人类可以查看完整历史
- 调试和审计需要

### 3. 理解 LLM 总结

```python
"Summarize this conversation for continuity. Include: 
 1) What was accomplished, 
 2) Current state, 
 3) Key decisions made."
```

**总结要点：**
- 已完成的工作
- 当前状态
- 关键决策

**不保留什么：**
- 具体代码片段
- 详细的工具输出
- 试错过程

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s06 | OpenClaw |
|------|----------------------|----------|
| **压缩触发** | tokens > 50000 | 无自动压缩 |
| **压缩方式** | LLM 总结 | 无（依赖 session 管理） |
| **持久化** | .transcripts/ JSONL | memory/ 目录 + MEMORY.md |
| **压缩粒度** | 整个对话 | 按 session 切分 |
| **恢复机制** | 读取 JSONL | 读取 memory 文件 |

**OpenClaw 的差异：**
- OpenClaw 用**多个 session** 避免 context 爆炸
- OpenClaw 的 memory 是**手动整理**的（不是自动总结）
- OpenClaw 有**session 交接**机制（session-chain-manager）

**可以借鉴的点：**
- 添加自动压缩功能
- 保存完整对话到 `.transcripts/`
- 在压缩前自动备份

---

## 📝 练习题

1. **添加手动压缩工具**：让 LLM 可以主动调用 `compact()`
2. **改进总结提示词**：添加更多总结维度（如"遇到的问题"）
3. **添加压缩历史**：记录每次压缩的时间和原因
4. **对比 OpenClaw**：我们的 session 管理和 s06 有什么区别？

---

## 🔗 下一步

- **s07 Task System** - 任务持久化（压缩后任务不丢失）
- **s11 Autonomous Agents** - 身份重新注入（压缩后恢复角色）
- **OpenClaw session-chain-manager** - 查看 `skills/session-chain-manager/SKILL.md`

---

*参考：OpenClaw 的 memory/ 目录和 SESSION_CHAIN_MANAGER skill*
