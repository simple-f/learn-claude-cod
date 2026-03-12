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
        result["content"] = f"[Previous: used {result.get('tool_use_id')}]"
    
    return messages
```

### Layer 2: auto_compact（第 65-90 行）

```python
def auto_compact(messages: list) -> list:
    # 1. 保存到 .transcripts/目录
    transcript_path = save_transcript(messages)
    
    # 2. 让 LLM 总结对话
    summary_messages = [
        {"role": "system", "content": "Summarize this conversation..."},
        *messages,
    ]
    summary = client.messages.create(...).content[-1].text
    
    # 3. 替换所有消息为摘要
    return [
        {"role": "system", "content": f"[Summary of previous conversation]\n{summary}"},
    ]
```

### Layer 3: compact 工具（第 18-35 行）

```python
COMPACT_TOOL = {
    "name": "compact",
    "description": "Summarize the conversation so far and continue.",
    "input_schema": {"type": "object", "properties": {}}
}
```

---

## 💡 学习要点

### 1. 理解三层压缩

**Layer 1: micro_compact（每回合）**
- 替换旧的 tool_result
- 保留最近 3 个
- 静默执行（LLM 不知道）

**Layer 2: auto_compact（超过阈值）**
- 保存完整对话
- 让 LLM 总结
- 替换为摘要

**Layer 3: compact 工具（手动触发）**
- Model 主动调用
- 立即总结
- 和 auto 一样

### 2. 理解压缩比例

```
典型对话（100 轮）：
- 原始大小：100,000 tokens
- micro_compact 后：70,000 tokens（30% 减少）
- auto_compact 后：2,000 tokens（97% 减少）

成本对比：
- 不压缩：$1.50/小时
- 压缩后：$0.03/小时
- 节省：98%
```

### 3. 理解摘要质量

**好的摘要：**
```
[Summary]
用户想要分析 Python 项目的代码质量。
已执行的操作：
1. 列出项目目录
2. 读取 setup.py
3. 运行 pylint 检查
待完成：
- 生成报告
- 提出改进建议
```

**差的摘要：**
```
[Summary]
用户问了一些问题，Agent 回答了一些内容。
```

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s06 | OpenClaw |
|------|----------------------|----------|
| **压缩触发** | token 数阈值 | 手动 + 定期 |
| **压缩方式** | LLM 总结 | 三层记忆架构 |
| **存储位置** | .transcripts/ 文件 | memory/YYYY-MM-DD.md |
| **摘要格式** | 自由文本 | 结构化（决策/任务/进展） |
| **恢复方式** | 读取摘要 | 读取 MEMORY.md + 日常笔记 |

**OpenClaw 的改进：**
- 三层记忆（热层/温层/冷层）
- 结构化摘要（便于搜索）
- 记忆持久化（跨会话）

---

## 🔬 深度技术解析

### 1. 为什么需要三层压缩？

**详细原理：**

这是**记忆曲线**的工程实现。

**心理学原理：**

```
艾宾浩斯遗忘曲线：
- 刚学的知识：100% 保留
- 1 天后：33% 保留
- 7 天后：25% 保留
- 30 天后：20% 保留

对应三层：
- 热层（最近 10 条）：完整保留（100%）
- 温层（10-50 条）：摘要（保留要点）
- 冷层（50 条以前）：关键决策（只保留 20%）
```

**为什么这样设计？**

```
问题：context 有限（通常 100K-200K tokens）

如果不压缩：
- 对话 100 轮后，context 满了
- 要么截断（丢失历史）
- 要么拒绝新对话

如果压缩：
- 保留最重要的信息
- 腾出空间给新对话
- 无限会话
```

**实际效果对比：**

```python
# ❌ 不压缩
messages = [所有历史对话]
# 100 轮后：50000 tokens
# 200 轮后：100000 tokens → 满了

# ✅ 压缩后
messages = [
    {"role": "system", "content": "历史摘要：讨论了 A、B、C 三个主题"},
    {"role": "system", "content": "关键决策：采用方案 X"},
    # 最近 10 轮完整对话
    ...
]
# 100 轮后：15000 tokens
# 200 轮后：18000 tokens → 还能继续
```

---

### 2. micro_compact 为什么保留 3 个？

**详细原理：**

这是**工作记忆容量**的工程近似。

**心理学研究：**

```
Miller's Law：
- 人类工作记忆容量 ≈ 7±2 个组块
- 最新鲜的记忆最清晰
- 3 是保守估计（保证质量）
```

**为什么是 3 不是 7？**

```
考虑因素：
1. token 成本：保留越多，成本越高
2. 相关性：最近的 tool_result 最相关
3. 平衡点：3 是成本和质量的平衡

测试数据：
- 保留 1 个：质量差（丢失太多）
- 保留 3 个：质量好（成本低）
- 保留 7 个：质量略好（成本翻倍）
- 保留 10+：质量不提升（成本过高）
```

**实际效果：**

```python
# 保留 3 个的效果
messages = [
    # 旧的 tool_result 被替换
    {"role": "user", "content": "[Previous: used bash]"},
    {"role": "user", "content": "[Previous: used read_file]"},
    
    # 最近 3 个保留完整
    {"role": "user", "content": [{"type": "tool_result", "content": "完整结果 1"}]},
    {"role": "user", "content": [{"type": "tool_result", "content": "完整结果 2"}]},
    {"role": "user", "content": [{"type": "tool_result", "content": "完整结果 3"}]},
]
```

---

### 3. 为什么让 LLM 自己总结？

**对比两种方案：**

```python
# ❌ 方案 1：规则式总结
def summarize(messages):
    # 提取关键信息
    files_read = [m for m in messages if "read_file" in str(m)]
    commands_run = [m for m in messages if "bash" in str(m)]
    
    return f"读取了{len(files_read)}个文件，执行了{len(commands_run)}个命令"

# 问题：
# - 丢失语义信息
# - 无法理解意图
# - 生硬不自然

# ✅ 方案 2：LLM 总结
def summarize(messages):
    summary_messages = [
        {"role": "system", "content": "Summarize this conversation..."},
        *messages,
    ]
    return client.messages.create(...).content
    
# 好处：
# - 保留语义信息
# - 理解意图和目标
# - 自然流畅
```

**成本计算：**

```
LLM 总结成本：
- 输入：50000 tokens
- 输出：500 tokens
- 成本：$0.0005（可以接受）

收益：
- 压缩到 500 tokens
- 保留关键信息
- 自然流畅
```

---

## 📝 练习题

1. **添加压缩统计**：记录每次压缩节省的 tokens
2. **实现自定义规则**：保留特定类型的 tool_result
3. **改进摘要质量**：添加摘要评估机制
4. **对比 OpenClaw**：分析 MEMORY.md 的结构

---

## 🔗 下一步

- **s07 Task System** - 任务持久化（JSON 文件存储）
- **s08 Background Tasks** - 后台任务（异步执行）
- **s11 Autonomous Agents** - 自主任务认领

---

*参考：OpenClaw 的 memory/ 目录和三层记忆架构*
