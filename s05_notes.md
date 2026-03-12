# s05 Skill Loading - 学习笔记

## 📌 核心洞察

> **"Don't put everything in the system prompt. Load on demand."**

这是 s05 最重要的设计思想：**按需加载技能，而不是把所有指令都塞进系统提示词**。

---

## 🔑 双层注入架构

### Layer 1：技能元数据（便宜）

```python
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
  - pdf: Process PDF files...        [tags: file,media]
  - code-review: Review code...      [tags: quality,git]
  - security: Security best practices [tags: safety]
"""
```

**特点：**
- 每个技能 ~100 tokens
- 只包含名称 + 简短描述
- LLM 知道有什么可用

### Layer 2：完整技能内容（按需）

```python
# 当 LLM 调用 load_skill("pdf") 时：
tool_result:
<skill name="pdf">
  Full PDF processing instructions
  Step 1: Extract text using PyMuPDF
  Step 2: Analyze structure...
  Step 3: Generate summary...
</skill>
```

**特点：**
- 完整指令（可能几千 tokens）
- 只在需要时加载
- 用完即弃（不占 context）

---

## 🏗️ 目录结构

```
skills/
  pdf/
    SKILL.md          # frontmatter + body
  code-review/
    SKILL.md
  security/
    SKILL.md
```

### SKILL.md 格式

```markdown
---
name: pdf
description: Process PDF files
tags: file,media
---

# PDF Processing Skill

## Steps
1. Extract text using PyMuPDF
2. Analyze structure...
3. Generate summary...
```

**Frontmatter（YAML）：**

| 字段 | 作用 | 示例 |
|------|------|------|
| `name` | 技能标识 | `pdf` |
| `description` | 简短描述 | "Process PDF files" |
| `tags` | 标签（用于搜索） | `file,media` |

---

## 💡 学习要点

### 1. 理解按需加载

**对比两种方案：**

```python
# ❌ 方案 1：全部塞进 system prompt
SYSTEM = """
你是一个编码助手。

技能 1：PDF 处理
- 步骤 1：用 PyMuPDF 提取文本
- 步骤 2：分析结构
...（1000 tokens）

技能 2：代码审查
- 步骤 1：检查代码规范
- 步骤 2：查找潜在 bug
...（1000 tokens）

技能 3：安全最佳实践
...（1000 tokens）
"""

# 问题：
# - 每次调用都带 3000+ tokens
# - 即使用户只问"Hello"，也要为这些 tokens 付费
# - LLM 可能被过多信息干扰

# ✅ 方案 2：按需加载
SYSTEM = """你是一个编码助手。
可用技能：pdf, code-review, security
用 load_skill 加载需要的技能。"""

# 好处：
# - 初始只有 100 tokens
# - 用户问 PDF 问题时才加载 pdf 技能
# - 节省 90%+ tokens
```

### 2. 理解工具注入

```python
# load_skill 工具返回的内容格式
{
    "role": "user",
    "content": "<skill name='pdf'>完整指令...</skill>"
}
```

**为什么用 XML 标签？**

```
好处：
1. 清晰标记开始和结束
2. LLM 容易识别技能内容
3. 可以嵌套多个技能

对比：
- 纯文本：LLM 不知道哪里是技能内容
- JSON：需要转义，可读性差
- XML：清晰、易读、易解析
```

### 3. 理解技能发现

```python
# 自动扫描 skills/ 目录
def load_skills_metadata() -> str:
    skills_list = []
    for skill_dir in Path("skills").iterdir():
        if skill_dir.is_dir():
            skill_meta = parse_frontmatter(skill_dir / "SKILL.md")
            skills_list.append(f"  - {skill_meta['name']}: {skill_meta['description']}")
    return "\n".join(skills_list)
```

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s05 | OpenClaw |
|------|----------------------|----------|
| **技能存储** | 文件目录（SKILL.md） | 相同 |
| **加载方式** | 工具调用 | 相同 |
| **注入格式** | XML 标签 | 相同 |
| **技能数量** | 3 个示例 | 38+ 内置技能 |
| **分类方式** | 标签（tags） | 分类 + 标签 |

**OpenClaw 的改进：**
- 技能分类（feishu-*, coding-*, automation-*）
- 技能依赖（某些技能需要前置技能）
- 技能版本控制（v1, v2）

---

## 🔬 深度技术解析

### 1. 为什么要通过 tool_result 注入技能？

**详细原理：**

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

### 2. 为什么用 XML 标签？

**详细原理：**

XML 标签提供**清晰的结构边界**。

**对比多种格式：**

```python
# ❌ 方案 1：纯文本
result = "PDF 处理技能：步骤 1... 步骤 2..."
# 问题：LLM 不知道哪里是技能内容

# ❌ 方案 2：JSON
result = json.dumps({"skill": "pdf", "content": "..."})
# 问题：需要转义，LLM 解析困难

# ✅ 方案 3：XML
result = "<skill name='pdf'>完整指令...</skill>"
# 好处：
# - 清晰标记开始和结束
# - LLM 容易识别
# - 人类可读
```

**实际效果：**

```python
# LLM 看到的内容
messages = [
    {"role": "user", "content": "怎么处理 PDF？"},
    {"role": "assistant", "content": "我加载 PDF 技能"},
    {"role": "user", "content": [
        {"type": "tool_result", "content": """
<skill name='pdf'>
  # PDF 处理技能
  
  ## 步骤
  1. 用 PyMuPDF 提取文本
  2. 分析结构
  3. 生成摘要
</skill>
        """}
    ]},
]
```

---

### 3. 技能元数据设计

**为什么需要元数据？**

```
问题：
- 有 38+ 个技能
- 不能全部塞进 system prompt（太贵）
- 需要让 LLM 知道有什么可用

解决：
- 每个技能 100 tokens 元数据
- 总共 3800 tokens（可接受）
- LLM 根据需要选择加载
```

**元数据内容：**

```yaml
name: pdf                    # 技能标识（用于调用）
description: Process PDF     # 简短描述（LLM 决定何时用）
tags: file,media             # 标签（用于搜索）
version: 1.0                 # 版本号（可选）
author: ai2                  # 作者（可选）
```

**扩展设计：**

```yaml
# 高级功能
dependencies:                # 依赖其他技能
  - markdown
conflicts:                   # 冲突技能
  - image-ocr
required_tools:              # 需要的工具
  - read_file
  - write_file
```

---

## 📝 练习题

1. **添加技能搜索**：根据标签搜索技能
2. **实现技能缓存**：加载过的技能缓存到内存
3. **添加技能版本**：支持多版本共存
4. **对比 OpenClaw**：找一个 skill 文件，分析结构

---

## 🔗 下一步

- **s06 Context Compact** - 上下文压缩（三层记忆）
- **s07 Task System** - 任务持久化
- **s09 Agent Teams** - 多 Agent 协作

---

*参考：OpenClaw skills 目录 `~/.openclaw/workspace-ai1/skills/`*
