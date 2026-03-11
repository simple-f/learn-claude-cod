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
- `name` - 技能名称
- `description` - 简短描述（用于 Layer 1）
- `tags` - 标签（方便搜索）

**Body（Markdown）：**
- 完整指令
- 步骤说明
- 最佳实践

---

## 🔧 SkillLoader 类（第 35-72 行）

```python
class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self._load_all()  # 启动时扫描所有技能

    def _parse_frontmatter(self, text: str) -> tuple:
        """解析 YAML frontmatter（--- 分隔符之间）"""
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        # 返回 meta 字典 + body 文本

    def get_descriptions(self) -> str:
        """Layer 1: 返回所有技能的简短描述"""
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            lines.append(f"  - {name}: {desc}")

    def get_content(self, name: str) -> str:
        """Layer 2: 返回指定技能的完整内容"""
        skill = self.skills.get(name)
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"
```

---

## 💡 学习要点

### 1. 理解 Token 经济性

**传统方式（全塞进 system prompt）：**
```
10 个技能 × 500 tokens = 5000 tokens（每次对话都烧钱）
```

**按需加载方式：**
```
Layer 1: 10 个技能 × 20 tokens = 200 tokens（固定）
Layer 2: 只用 1 个技能 = 500 tokens（按需）
总计：700 tokens（节省 86%）
```

### 2. 理解发现机制

```python
for f in sorted(self.skills_dir.rglob("SKILL.md")):
    # 自动扫描 skills/ 目录下所有 SKILL.md
    # 不需要手动注册
```

**好处：**
- 添加新技能只需放一个文件
- 自动发现，无需修改代码
- 符合开闭原则

### 3. 理解 XML 包装

```python
return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"
```

**为什么用 XML 标签？**
- 清晰边界（LLM 知道哪里开始/结束）
- 方便解析（可以用正则提取）
- 避免指令注入（隔离技能内容）

---

## 🆚 与 OpenClaw 对比

| 维度 | learn-claude-code s05 | OpenClaw |
|------|----------------------|----------|
| **技能存储** | `skills/<name>/SKILL.md` | `skills/<name>/SKILL.md`（相同） |
| **加载方式** | 启动时扫描 + 按需加载 | 启动时扫描 + 工具系统路由 |
| **技能描述** | YAML frontmatter | YAML frontmatter（相同） |
| **注入方式** | Layer 1 + Layer 2 | 工具系统 + 技能说明 |
| **技能数量** | 动态扩展 | 38+ 内置技能 |

**OpenClaw 的差异：**
- OpenClaw 的 Skills 系统更复杂（支持工具调用）
- OpenClaw 的技能可以触发外部 API（飞书、GitHub 等）
- learn-claude-code 更纯粹（教学目的）

---

## 📝 练习题

1. **添加技能搜索**：实现 `search_skill(keyword)` 工具
2. **添加技能缓存**：加载过的技能缓存在内存
3. **添加技能依赖**：技能 A 依赖技能 B（自动加载）
4. **对比 OpenClaw**：找一个 OpenClaw skill，分析它和 s05 的区别

---

## 🔗 下一步

- **s06 Context Compact** - 上下文压缩（节省 tokens）
- **s09 Agent Teams** - 多 Agent 协作（技能共享）
- **OpenClaw Skills** - 查看 `~/.openclaw/workspace-ai1/skills/` 目录

---

*参考：OpenClaw skills 目录结构和 SKILL.md 规范*
