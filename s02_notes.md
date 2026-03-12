# s02 Tool Use - 学习笔记

## 📌 核心洞察

> **"The loop didn't change at all. I just added tools."**

这是 s02 最重要的设计思想：**核心循环不变，通过扩展工具数组来增加功能**。

这就是**开闭原则**（Open-Closed Principle）：
- 对扩展开放（加新工具）
- 对修改封闭（不用改循环代码）

---

## 🔑 关键设计

### 1. 工具分发器（Dispatch Map）

```python
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}
```

**为什么用字典？**
- 快速查找：`handler = TOOL_HANDLERS.get(block.name)`
- 易于扩展：加新工具只需加一行
- 解耦：工具实现和调用逻辑分离

### 2. 安全路径检查

```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
```

**防止路径逃逸攻击：**
- `../../../etc/passwd` → ❌ 抛出异常
- `./test.txt` → ✅ 允许

### 3. 工具定义格式

```python
TOOLS = [
    {"name": "bash", "description": "...",
     "input_schema": {"type": "object", "properties": {...}, "required": [...]}},
    ...
]
```

这是 **Anthropic Function Calling** 的标准格式，告诉 LLM：
- 工具名称
- 工具描述（LLM 根据这个决定何时调用）
- 参数 schema（类型、必填项）

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s02 | OpenClaw |
|------|----------------------|----------|
| **工具注册** | 硬编码字典 | Skills 系统（自动发现） |
| **工具数量** | 4 个 | 38+ 内置技能 |
| **安全机制** | 路径检查 + 命令黑名单 | 多层护栏 + 权限控制 |
| **扩展方式** | 修改 TOOL_HANDLERS | 添加 skill 文件 |
| **工具类型** | bash, read, write, edit | 飞书、GitHub、浏览器等 |

### OpenClaw 的 Skills 系统

OpenClaw 的 skills 在 `skills/` 目录下，每个 skill 是一个独立的 `.md` 文件：

```
skills/
├── feishu-doc/
│   └── SKILL.md      # 飞书文档操作
├── github/
│   └── SKILL.md      # GitHub 操作
├── coding-agent/
│   └── SKILL.md      # 代码代理
└── ...
```

**对比分析：**

| 方面 | learn-claude-code | OpenClaw |
|------|------------------|----------|
| **组织方式** | 代码内字典 | 文件目录 |
| **加载方式** | 启动时硬编码 | 运行时自动发现 |
| **描述格式** | 简单字符串 | SKILL.md 规范 |
| **工具调用** | 直接函数调用 | 工具系统路由 |

---

## 💡 学习要点

### 1. 理解 Dispatch 模式

```
LLM 调用 → 工具名 → 字典查找 → 执行函数 → 返回结果
```

这是**策略模式**的简化版，核心是**用数据驱动行为**。

### 2. 理解安全边界

- **路径安全**：`safe_path()` 防止逃逸
- **命令安全**：黑名单过滤危险命令
- **输出安全**：截断长输出（50000 字符）

### 3. 理解可扩展性

添加新工具的步骤：
1. 写处理函数 `run_new_tool(...)`
2. 在 `TOOL_HANDLERS` 注册
3. 在 `TOOLS` 数组添加定义

**不用改 agent_loop！**

---

## 🔬 深度技术解析

### 1. 为什么用字典做工具分发？

**详细原理：**

这是**策略模式**的简化实现，利用字典的 O(1) 查找特性。

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

**性能对比：**

| 方面 | if-else | match-case | 字典 |
|------|---------|------------|------|
| **查找速度** | O(n) | O(n) | O(1) |
| **代码行数** | 多 | 中 | 少 |
| **扩展性** | 差 | 中 | 好 |
| **可读性** | 中 | 好 | 好 |

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

### 2. safe_path 防路径逃逸攻击

**详细原理：**

这是**路径穿越攻击**（Path Traversal Attack）的防御。

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

### 3. 工具定义格式详解

**为什么是这种格式？**

这是 **Anthropic Function Calling** 的标准格式，设计考虑：

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

**每个字段的作用：**

| 字段 | 作用 | LLM 如何使用 |
|------|------|-------------|
| `name` | 工具标识 | 匹配要调用的工具 |
| `description` | 工具说明 | 决定何时调用 |
| `input_schema` | 参数定义 | 决定传什么参数 |

**为什么用 JSON Schema？**

```python
# 好处 1：类型检查
"command": {"type": "string"}  # LLM 知道这是字符串

# 好处 2：必填验证
"required": ["command"]  # LLM 知道必须传这个

# 好处 3：枚举约束
"status": {"type": "string", "enum": ["pending", "completed"]}
# LLM 知道只能选这两个值
```

---

## 📝 练习题

1. **添加 `list_dir` 工具**：列出目录内容
2. **添加 `search_file` 工具**：搜索文件内容
3. **改进安全检查**：用白名单替代黑名单
4. **对比 OpenClaw**：找一个 skill，分析它和 s02 的区别

---

## 🔗 下一步

- **s04 Subagent** - 如何派生子任务（对标 `sessions_spawn`）
- **s05 Skill Loading** - 如何动态加载技能（对标 Skills 系统）
- **s09 Agent Teams** - 多 Agent 协作（对标飞书 A2A）

---

*参考：OpenClaw skills 目录 `~/.openclaw/workspace-ai1/skills/`*
