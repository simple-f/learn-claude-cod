# s01-s12 详细技术解析

> 补充说明：为什么这样做？背后的原理是什么？

---

## 📖 使用说明

本文档是对 s01-s12 学习笔记的**深度补充**，重点解释：

1. **关键步骤的原理** - 为什么这样做？
2. **设计决策的权衡** - 为什么不那样做？
3. **底层机制** - 实际发生了什么？
4. **常见误区** - 初学者容易犯的错误

---

## s01 Agent Loop - 深度解析

### 1.1 为什么要把工具结果加回 messages？

**问题：** 很多初学者不理解这行代码的作用：

```python
messages.append({"role": "user", "content": results})  # 关键！
```

**详细解释：**

LLM（大语言模型）是**无状态**的。这意味着：

```
第 1 次调用：
你： "执行命令 ls"
LLM: {"tool_use": "bash", "command": "ls"}

第 2 次调用（如果不加结果）：
你： "执行命令 ls"
LLM: {"tool_use": "bash", "command": "ls"}  # 完全一样！
```

LLM 不知道工具执行了什么，它只是根据输入生成输出。

**正确的流程：**

```
第 1 次调用：
你： "执行命令 ls"
LLM: {"tool_use": "bash", "command": "ls"}

你： "工具执行结果是：file1.txt, file2.txt"
LLM: "好的，目录中有两个文件"  # 现在它知道了
```

**这就是 ReAct 模式的核心：**

```
Reason（推理）→ Act（行动）→ Observe（观察）→ Reason（推理）→ ...
```

每次循环都要把观察结果告诉 LLM，它才能：
- 判断任务是否完成
- 决定下一步做什么
- 根据输出调整策略

**类比人类思考：**

```
你： "我要写一个 Python 脚本"
   ↓
打开编辑器（行动）
   ↓
看到空白屏幕（观察）
   ↓
"好的，现在开始写代码"（新的推理）
```

如果你闭上眼睛（没有观察），你就不知道屏幕是空白的，也就不知道下一步该做什么。

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

### 1.2 为什么 stop_reason != "tool_use" 就返回？

**问题：** 这个判断条件的含义是什么？

```python
if response.stop_reason != "tool_use":
    return  # 模型说完成了
```

**详细解释：**

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

**对比人类：**

```
老板： "帮我查一下天气"
你： "好的，我打开手机天气应用"（tool_use）
    "查到了，今天 25 度"（end_turn）

如果你一直说"我要查天气"但不动手，老板会问："你到底查了没？"
```

---

### 1.3 为什么 max_tokens 设为 8000？

**问题：** 这个数字是怎么来的？

```python
response = client.messages.create(
    ...,
    max_tokens=8000,
)
```

**详细解释：**

`max_tokens` 是 LLM 单次响应的**最大输出长度**。

**计算方式：**

```
1 个 token ≈ 4 个英文字符 ≈ 2 个汉字

8000 tokens ≈ 32000 英文字符 ≈ 16000 汉字
```

**为什么是 8000？**

这是 Claude 3 系列的**推荐值**：

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

---

## s02 Tool Use - 深度解析

### 2.1 为什么用字典做工具分发？

**问题：** 为什么要这样写？

```python
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    ...
}
```

**详细解释：**

这是**策略模式**的简化实现。

**替代方案对比：**

```python
# ❌ 方案 1：if-else 链
if tool_name == "bash":
    result = run_bash(...)
elif tool_name == "read_file":
    result = run_read(...)
elif tool_name == "write_file":
    result = run_write(...)
# ... 每加一个工具就多一层

# ❌ 方案 2：match-case（Python 3.10+）
match tool_name:
    case "bash":
        result = run_bash(...)
    case "read_file":
        result = run_read(...)
    # ... 还是冗长

# ✅ 方案 3：字典查找
handler = TOOL_HANDLERS.get(tool_name)
if handler:
    result = handler(**params)
```

**字典方案的优势：**

| 方面 | if-else | match-case | 字典 |
|------|---------|------------|------|
| **查找速度** | O(n) | O(n) | O(1) |
| **代码行数** | 多 | 中 | 少 |
| **扩展性** | 差 | 中 | 好 |
| **可读性** | 中 | 好 | 好 |

**实际执行流程：**

```
LLM 调用 → 工具名 "bash"
           ↓
    TOOL_HANDLERS.get("bash")
           ↓
    lambda **kw: run_bash(kw["command"])
           ↓
    执行 run_bash("ls -la")
           ↓
    返回结果
```

**为什么用 lambda？**

```python
# ❌ 直接存函数引用
TOOL_HANDLERS = {
    "bash": run_bash,  # 问题：参数不匹配
}

# LLM 调用时传的是 kwargs：{"command": "ls"}
# 但 run_bash 需要的是 positional：run_bash(command)

# ✅ 用 lambda 包装
TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
}

# 现在可以统一调用：handler(**kwargs)
```

---

### 2.2 为什么需要 safe_path 检查？

**问题：** 这个函数是干什么的？

```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
```

**详细解释：**

这是**路径逃逸攻击**的防御。

**攻击场景：**

```python
# 用户（或恶意 LLM）输入：
path = "../../../etc/passwd"

# 如果没有检查：
WORKDIR = "/app/workspace"
full_path = WORKDIR / path
# 结果："/app/workspace/../../../etc/passwd"
#       = "/etc/passwd"  ← 访问了系统文件！
```

**safe_path 的工作原理：**

```python
# 1. 拼接路径
path = (WORKDIR / p).resolve()
# "/app/workspace" / "../../../etc/passwd"
# = "/etc/passwd"（resolve 会解析 ..）

# 2. 检查是否在 WORKDIR 内
if not path.is_relative_to(WORKDIR):
    # "/etc/passwd".is_relative_to("/app/workspace")
    # = False → 抛出异常
    raise ValueError(...)
```

**测试用例：**

```python
# ✅ 允许的路径
safe_path("./test.txt")           # /app/workspace/test.txt
safe_path("subdir/file.txt")      # /app/workspace/subdir/file.txt
safe_path("../workspace/file.txt") # /app/workspace/file.txt

# ❌ 禁止的路径
safe_path("../etc/passwd")        # 抛出异常
safe_path("/etc/passwd")          # 抛出异常
safe_path("../../home/user/.ssh/id_rsa")  # 抛出异常
```

**为什么不用字符串检查？**

```python
# ❌ 错误的做法
if ".." in path:
    raise ValueError()

# 绕过方法：
path = "....//....//etc/passwd"  # 没有 ".." 但解析后是 "/etc/passwd"

# ✅ 正确的做法：用 resolve() 规范化后再检查
```

---

## s03 TodoWrite - 深度解析

### 3.1 为什么限制只能有 1 个 in_progress？

**问题：** 这个验证规则的意义是什么？

```python
in_progress_count = sum(1 for item in items if item["status"] == "in_progress")
if in_progress_count > 1:
    raise ValueError("Only one task can be in_progress at a time")
```

**详细解释：**

这是**强制单线程工作**的设计。

**多任务并行的问题：**

```
任务 A: 写登录功能（进行中）
任务 B: 写注册功能（进行中）
任务 C: 写支付功能（进行中）
```

LLM 可能会：
- 在任务 A 和 B 之间跳来跳去
- 忘记任务 A 写到哪了
- 代码风格不一致

**单线程的好处：**

```
任务 A: 写登录功能（进行中）
任务 B: 写注册功能（等待）
任务 C: 写支付功能（等待）

完成 A → 标记 completed
开始 B → 标记 in_progress
```

**心理学原理：**

这是基于**注意力管理**的研究：
- 人类同时只能专注 1 个复杂任务
- 上下文切换成本高（平均 23 分钟恢复专注）
- LLM 也有类似问题（context 污染）

**对比其他系统：**

| 系统 | 并发限制 | 原因 |
|------|----------|------|
| **s03 TodoWrite** | 1 个 in_progress | 强制专注 |
| **OpenClaw** | 无限制 | 多 Agent 协作 |
| **Jira** | 无限制 | 团队并行 |
| **GTD** | 1 个 next action | 个人生产力 |

**什么时候可以放宽？**

```python
# 场景：多个独立任务
任务 A: 修改文件 A.py
任务 B: 修改文件 B.py  # 不影响 A

# 可以改为：
MAX_IN_PROGRESS = 3  # 允许最多 3 个进行中
```

---

### 3.2 为什么最多 20 个待办？

**问题：** 这个数字是怎么来的？

```python
if len(items) > 20:
    raise ValueError("Too many items")
```

**详细解释：**

这是**认知负荷**的限制。

**心理学研究：**

- **Miller's Law**：人类工作记忆容量 ≈ 7±2 个组块
- **任务管理最佳实践**：待办列表 ≤ 10-20 项

**为什么限制？**

```python
# ❌ 无限制的情况
todo_list = [
    "#1: 任务 A",
    "#2: 任务 B",
    ...
    "#50: 任务 AX",  # LLM 会迷失
]

# LLM 看到 50 个任务：
# "我该从哪开始？"
# "这个任务做完了吗？"
# "要不要先做别的？"
```

**20 是怎么算的？**

```
显示限制：
- 终端高度：通常 24-40 行
- 每个任务占 2 行：[ ] #1: 任务描述
- 留出空间给其他输出：24 - 4 = 20 行

认知限制：
- 7±2 是瞬时记忆
- 20 是可管理上限
- 超过 20 就要分组/分页
```

**如果任务真的很多怎么办？**

```python
# 方案 1：分组
项目 A（5 个任务）
项目 B（5 个任务）
项目 C（5 个任务）

# 方案 2：分页
显示最近 10 个，其他的归档

# 方案 3：分解
大任务 → 子任务 → 孙任务（树状结构）
```

---

## s04 Subagent - 深度解析

### 4.1 为什么要给子 agent 独立的 messages？

**问题：** 为什么这样写？

```python
# 创建子 agent 时，给它全新的 messages 列表
subagent_messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": task_description}
]
```

**详细解释：**

这是**上下文隔离**的设计。

**对比两种方案：**

```python
# ❌ 方案 1：共享 messages
subagent_messages = parent_messages.copy()  # 继承父 agent 的所有历史

# 问题：
# 1. 子 agent 看到父 agent 的所有对话，可能混淆
# 2. tokens 浪费（很多上下文不相关）
# 3. 子 agent 可能被父 agent 的错误误导

# ✅ 方案 2：独立 messages
subagent_messages = [
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
老板： "帮我写个登录功能"

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

## s05 Skill Loading - 深度解析

### 5.1 为什么要通过 tool_result 注入技能？

**问题：** 为什么不用 system prompt？

```python
# ✅ 正确做法：通过 tool_result 注入
messages.append({
    "role": "user",
    "content": [{"type": "tool_result", "content": skill_content}]
})

# ❌ 错误做法：塞进 system prompt
system_prompt += f"\n\nSkills:\n{skill_content}"
```

**详细解释：**

这是**上下文效率**的优化。

**对比分析：**

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **system prompt** | 永久有效 | 占用每个请求的 tokens | 核心规则 |
| **tool_result** | 按需加载 | 只在当前轮有效 | 技能/知识 |

**为什么 skill 适合用 tool_result？**

```
场景：用户问"怎么飞书文档操作？"

❌ system prompt 方式：
- 每次调用都包含飞书技能（即使用户没问）
- 浪费 tokens
- 可能干扰其他任务

✅ tool_result 方式：
- 用户问到时才加载
- 只占用一次请求
- 任务完成后就"忘记"
```

**底层机制：**

```
LLM 的注意力机制：
- system prompt：始终关注（权重高）
- tool_result：当前轮关注（权重中）
- 历史消息：逐渐衰减（权重低）

技能是"临时知识"，适合用 tool_result。
```

---

## s06 Context Compact - 深度解析

### 6.1 为什么要三层压缩？

**问题：** 这个设计是怎么来的？

```python
# 三层结构
热层（最近 10 条）：完整保留
温层（10-50 条）：摘要
冷层（50 条以前）：关键决策
```

**详细解释：**

这是**记忆曲线**的工程实现。

**心理学原理：**

```
艾宾浩斯遗忘曲线：
- 刚学的知识：100% 保留
- 1 天后：33% 保留
- 7 天后：25% 保留
- 30 天后：20% 保留

对应三层：
- 热层：刚发生的对话（100% 保留）
- 温层：最近的对话（摘要，保留要点）
- 冷层：很久以前的（只保留关键决策）
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

## s07-s12 待续...

---

**文档版本：** v1.1  
**最后更新：** 2026-03-12 15:15  
**作者：** ai2 (claw 后端机器人)

**更新日志：**
- v1.0: s01-s03 详细解析
- v1.1: 补充 s04-s06 深度解析
