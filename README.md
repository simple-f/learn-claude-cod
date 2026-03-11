# Learn Claude Code

🤖 **从零构建 AI Agent 框架的教学项目**

本项目是 [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（24,826+ ⭐）的学习笔记和代码注解版本。通过 12 个模块，从最基础的 Agent 循环开始，逐步构建完整的多 Agent 协作系统。

## 🎯 项目目标

- **理解 AI Agent 核心原理**：从第一行代码开始构建，不依赖黑盒框架
- **掌握关键设计模式**：ReAct 循环、工具调用、子代理、团队协作
- **对比实战**：与 OpenClaw 项目对照学习，理解生产级 Agent 系统设计

## 📚 适用人群

- 想理解 AI Agent 内部工作原理的开发者
- 想构建自己的 Agent 框架的工程师
- OpenClaw 用户想深入了解底层实现

## 📊 学习路径

```
阶段一：核心循环（第 1-2 天）
  s01 → s02
     ↓
阶段二：规划与知识（第 3-5 天）
  s03 → s04 → s05 → s06
     ↓
阶段三：持久化（第 6-7 天）
  s07 → s08
     ↓
阶段四：团队协作（第 8-10 天）
  s09 → s10 → s11 → s12
```

## 📁 本地文件状态

| 模块 | 主题 | 代码 | 注解 | 笔记 |
|------|------|------|------|------|
| s01 | Agent Loop | ✅ | ✅ | ✅ |
| s02 | Tool Use | ✅ | ✅ | ✅ |
| s03 | Todo Write | ✅ | ⏳ | ✅ |
| s04 | Subagent | ✅ | ⏳ | ✅ |
| s05 | Skill Loading | ✅ | ⏳ | ✅ |
| s06 | Context Compact | ✅ | ⏳ | ✅ |
| s07 | Task System | ✅ | ⏳ | ✅ |
| s08 | Background Tasks | ✅ | ⏳ | ✅ |
| s09 | Agent Teams | ✅ | ⏳ | ✅ |
| s10 | Team Protocols | ✅ | ⏳ | ✅ |
| s11 | Autonomous Agents | ✅ | ⏳ | ✅ |
| s12 | Worktree Isolation | ❌ 原仓库无 | - | - |

**当前进度：11/12 模块代码 + 11/12 模块笔记**（s12 原仓库不存在）

---

## 📚 课程目录

> **说明**：当前仓库包含全部 11 个模块的代码和详细笔记。每个模块都有核心概念、代码分析、与 OpenClaw 对比和练习题。

### 第 1 课：Agent 核心循环 (s01)

**文件：** `s01_agent_loop.py` | `s01_notes.md`

**学习内容：**
- **Agent Loop 模式**：所有 AI Agent 的核心——无限循环
  ```
  问 LLM → 调用工具 → 执行 → 反馈结果 → 重复
  ```
- **ReAct 模式**：Reason + Act 循环
- **工具定义格式**：Anthropic Function Calling 标准
- **安全检查**：危险命令黑名单过滤

**核心代码：**
- 第 60-77 行：核心循环实现
- 第 26-35 行：工具定义
- 第 40-50 行：安全检查

**关键理解：**
- LLM 是无状态的，必须把工具结果"喂"回去
- `messages` 列表就是 Agent 的"记忆"

---

### 第 2 课：工具系统扩展 (s02)

**文件：** `s02_tool_use.py` | `s02_tool_use_annotated.py` | `s02_notes.md`

**学习内容：**
- **开闭原则**：核心循环不变，通过扩展工具数组增加功能
- **Dispatch Map 模式**：用字典分发工具调用
- **路径安全检查**：防止 `../../../etc/passwd` 逃逸攻击
- **工具定义 Schema**：告诉 LLM 工具名称、描述、参数

**新增工具：**
- `bash` - 执行 shell 命令
- `read_file` - 读取文件（支持行数限制）
- `write_file` - 写入文件
- `edit_file` - 精确文本替换

---

### 第 3 课：任务管理 (s03)

**文件：** `s03_todo_write.py` | `s03_notes.md`

**学习内容：**
- **TodoManager 类**：结构化任务追踪
- **状态管理**：pending / in_progress / completed
- **验证规则**：最多 20 项、只能有 1 个 in_progress
- **渲染格式**：`[>] #2: 任务 B`（视觉提示）

**核心代码：**
- 第 33-72 行：TodoManager 类
- 第 155-175 行：todo 工具定义

**关键理解：**
- 外部化状态（不占用 context tokens）
- 强制专注（只能有 1 个进行中任务）
- 人类可见的进度追踪

---

### 第 4 课：子 Agent 系统 (s04)

**文件：** `s04_subagent.py` | `s04_notes.md`

**学习内容：**
- **上下文隔离**：子 Agent 有全新的 `messages=[]`
- **进程隔离**：父 Agent 上下文保持干净
- **任务委派**：通过 `task` 工具派生子任务
- **权限分离**：子 Agent 没有 `task` 工具（不能递归）

**架构图：**
```
Parent Agent                     Subagent
+------------------+             +------------------+
| messages=[...]   |             | messages=[]      | <-- 全新上下文
| tool: task       | ---------->| while tool_use:  |
| prompt="..."     |            |   执行工具       |
|                  | <--------- | return summary   |
+------------------+             +------------------+
```

**关键理解：**
- 子 Agent 上下文在完成后丢弃
- 只返回摘要（不返回完整对话）
- 可以并行派生多个子 Agent

---

### 第 5 课：技能加载 (s05)

**文件：** `s05_skill_loading.py` | `s05_notes.md`

**学习内容：**
- **双层注入架构**：Layer 1（元数据）+ Layer 2（完整内容）
- **Token 经济性**：按需加载，节省 86% tokens
- **技能目录**：`skills/<name>/SKILL.md`
- **YAML Frontmatter**：name / description / tags

**核心代码：**
- 第 35-72 行：SkillLoader 类
- Layer 1：`get_descriptions()` - 简短描述
- Layer 2：`get_content(name)` - 完整技能内容

**关键理解：**
- 不要把所有指令都塞进 system prompt
- 自动发现（扫描 skills 目录）
- XML 包装（清晰边界）

---

### 第 6 课：上下文压缩 (s06)

**文件：** `s06_context_compact.py` | `s06_notes.md`

**学习内容：**
- **三层压缩管道**：micro_compact → auto_compact → compact 工具
- **Layer 1**：替换旧 tool_result 为占位符（每回合）
- **Layer 2**：LLM 总结 + 保存到 `.transcripts/`（超过 50k tokens）
- **Layer 3**：手动触发压缩

**核心代码：**
- 第 37-63 行：micro_compact（静默执行）
- 第 66-90 行：auto_compact（自动触发）
- 第 30-33 行：token 估算

**关键理解：**
- 战略性遗忘（保持关键信息）
- 持久化备份（.transcripts/ JSONL）
- LLM 总结（2000 tokens 以内）

---

### 第 7 课：任务系统 (s07)

**文件：** `s07_task_system.py` | `s07_notes.md`

**学习内容：**
- **任务持久化**：`.tasks/task_<id>.json`
- **依赖图**：blockedBy / blocks 双向关联
- **自动解锁**：完成任务后自动解除依赖
- **状态管理**：pending / in_progress / completed

**核心代码：**
- 第 33-104 行：TaskManager 类
- 第 86-91 行：`_clear_dependency()` - 自动解锁

**关键理解：**
- 外部状态（压缩后不丢失）
- 双向依赖（A blocks B → B blockedBy A）
- 多 Agent 共享任务板

---

### 第 8 课：后台任务 (s08)

**文件：** `s08_background_tasks.py` | `s08_notes.md`

**学习内容：**
- **线程模型**：主线程不阻塞，后台并行执行
- **通知队列**：drain_notifications() 注入结果
- **线程安全**：Lock 保护共享数据
- **超时控制**：300 秒超时

**核心代码：**
- 第 32-84 行：BackgroundManager 类
- 第 40-52 行：`run()` - 启动后台线程
- 第 68-77 行：`drain_notifications()` - 排出通知

**关键理解：**
- Fire and forget（发射后不管）
- 并行执行（多个任务同时运行）
- 通知队列（解耦主线程和后台）

---

### 第 9 课：Agent 团队协作 (s09)

**文件：** `s09_agent_teams.py` | `s09_notes.md`

**学习内容：**
- **持久化 Agent**：spawn → work → idle → work（不是用完即弃）
- **JSONL 信箱**：每个队友独立的 `.jsonl` 收件箱
- **5 种消息类型**：message / broadcast / shutdown_request / shutdown_response / plan_approval_response
- **轮询机制**：5 秒间隔检查收件箱

**架构图：**
```
.team/inbox/
  alice.jsonl
  bob.jsonl
  lead.jsonl

send_message("alice", "fix bug"):
  open("alice.jsonl", "a").write(msg)

read_inbox("alice"):
  msgs = [json.loads(l) for l in ...]
  open("alice.jsonl", "w").close()  # drain
```

**关键理解：**
- 追加写入（不覆盖历史）
- 读取后清空（drain 模式）
- 异步通信（发送者不等待）

---

### 第 10 课：团队协议 (s10)

**文件：** `s10_team_protocols.py` | `s10_notes.md`

**学习内容：**
- **关闭协议**：shutdown_request → shutdown_response
- **计划审批协议**：plan_approval → plan_approval_response
- **request_id 关联**：用唯一 ID 关联请求和响应
- **状态机**：pending → approved | rejected

**架构图：**
```
Shutdown FSM:
Lead                              Teammate
+---------------------+          +---------------------+
| shutdown_request     | -------> | receives request    |
| {request_id: abc}    |          | decides: approve?   |
+---------------------+          +---------------------+
| shutdown_response    | <------- | shutdown_response   |
| {approve: true}      |          | {approve: true}     |
+---------------------+          +---------------------+
```

**关键理解：**
- 同一个 request_id 模式，两个应用领域
- 优雅关闭（不是强制杀死）
- 异步审批（支持并发请求）

---

### 第 11 课：自主 Agent (s11)

**文件：** `s11_autonomous_agents.py` | `s11_notes.md`

**学习内容：**
- **空闲循环**：poll every 5s for up to 60s
- **任务认领**：scan .tasks/ → unclaimed? → claim
- **身份重新注入**：压缩后恢复角色信息
- **超时关闭**：60 秒无工作 → shutdown

**核心代码：**
- 第 70-90 行：idle_cycle() - 空闲循环
- 第 92-103 行：scan_unclaimed_tasks() / claim_task()
- 第 106-120 行：create_identity_block()

**关键理解：**
- 自主寻找工作（不是被动等待）
- 任务板模式（去中心化分配）
- 身份持久化（压缩后恢复）

---

### 第 12 课：工作树隔离 (s12)

**状态：** ❌ 原仓库不存在此文件

**推测内容：**
- Git Worktree 使用
- 任务环境隔离
- 并行任务不冲突

---

**新增工具：**
- `bash` - 执行 shell 命令
- `read_file` - 读取文件（支持行数限制）
- `write_file` - 写入文件
- `edit_file` - 精确文本替换

**关键理解：**
- 添加新工具只需 3 步：写函数 → 注册 handler → 添加定义
- **不用改 agent_loop！**

---

### 第 4 课：子 Agent 系统 (s04)

**文件：** `s04_subagent.py`

**学习内容：**
- **进程隔离 = 上下文隔离**：子 Agent 有独立的 `messages=[]`
- **任务委派模式**：父 Agent 通过 `task` 工具派生子任务
- **摘要返回**：子 Agent 只返回总结，不返回完整上下文

**架构图：**
```
Parent Agent                    Subagent
+------------------+            +------------------+
| messages=[...]   |            | messages=[]      | <-- 全新上下文
| tool: task       | ---------> | while tool_use:  |
| prompt="..."     |            |   执行工具       |
|                  | <--------- | return summary   |
+------------------+            +------------------+
```

**关键理解：**
- 子 Agent 上下文在完成后丢弃
- 父 Agent 上下文保持干净
- 共享文件系统，隔离对话历史

---

### 第 9 课：Agent 团队协作 (s09)

**文件：** `s09_agent_teams.py`

**学习内容：**
- **持久化 Agent**：与子 Agent 不同，队友是持久的（spawn → work → idle → work）
- **JSONL 信箱通信**：每个队友有独立的 `.jsonl` 收件箱
- **5 种消息类型**：
  - `message` - 普通消息
  - `broadcast` - 广播消息
  - `shutdown_request` - 关闭请求（s10）
  - `shutdown_response` - 关闭响应（s10）
  - `plan_approval_response` - 计划审批（s10）

**架构图：**
```
.team/config.json              .team/inbox/
+------------------------+     +--------------+
| {"team_name": "...",   |     | alice.jsonl  |
|  "members": [...]}     |     | bob.jsonl    |
+------------------------+     | lead.jsonl   |
                               +--------------+

spawn_teammate("alice", "coder") → 独立线程运行 agent_loop
```

**关键理解：**
- 队友可以互相交谈（通过信箱）
- 追加写入，读取后清空（drain 模式）

---

### 第 10 课：团队协议 (s10)

**文件：** `s10_team_protocols.py`

**学习内容：**
- **关闭协议（Shutdown Protocol）**：
  ```
  Lead 发送 shutdown_request {request_id: abc}
     ↓
  Teammate 决定 approve/reject
     ↓
  Teammate 回复 shutdown_response {request_id: abc, approve: true}
     ↓
  Lead 更新状态 → "shutdown"，线程停止
  ```

- **计划审批协议（Plan Approval Protocol）**：
  ```
  Teammate 提交 plan_approval {plan: "..."}
     ↓
  Lead 审查计划文本
     ↓
  Lead 回复 plan_approval_response {approve: true/false}
  ```

- **请求 ID 关联模式**：用 `request_id` 关联请求和响应

**关键理解：**
- 同一个 `request_id` 关联模式，应用于两个领域
- 状态机：pending → approved | rejected

---

## 🔧 环境配置

### 前置要求

- Python 3.10+
- Anthropic API Key（或兼容的 API 服务）

### 安装依赖

```bash
pip install anthropic python-dotenv
```

### 配置环境变量

创建 `.env` 文件：

```bash
MODEL_ID=claude-sonnet-4-5-20250929
ANTHROPIC_BASE_URL=https://api.anthropic.com
# 或使用兼容服务
# ANTHROPIC_BASE_URL=http://localhost:8080
```

---

## 🚀 运行示例

### 运行第 1 课：基础 Agent

```bash
python s01_agent_loop.py
```

示例对话：
```
s01 >> 列出当前目录的文件
$ ls
file1.py file2.md
```

### 运行第 2 课：多工具

```bash
python s02_tool_use.py
```

支持工具：`bash`, `read_file`, `write_file`, `edit_file`

### 运行第 4 课：子 Agent

```bash
python s04_subagent.py
```

示例：
```
s04 >> 用 task 工具委派一个子任务
> task (explore): 查看项目结构
  发现了 3 个 Python 文件...
```

### 运行第 9/10 课：团队协作

```bash
python s09_agent_teams.py
python s10_team_protocols.py
```

---

## 📖 学习笔记

每节课都有对应的 `.md` 笔记文件，包含：

- 核心概念讲解
- 关键代码段分析
- 与 OpenClaw 对比
- 练习题
- 下一步学习建议

---

## 🔗 与 OpenClaw 对比

| 特性 | learn-claude-code | OpenClaw |
|------|------------------|----------|
| **Agent 循环** | 单次会话 | 常驻进程 + 心跳 |
| **工具系统** | 硬编码字典 | Skills 系统（38+ 内置） |
| **消息历史** | 内存列表 | 持久化到 session 文件 |
| **安全检查** | 简单黑名单 | 多层护栏 + 权限控制 |
| **人格系统** | 无 | SOUL.md（毒舌 PM） |
| **记忆系统** | 无 | MEMORY.md + 日常笔记 |
| **多 Agent** | 基础支持 | 飞书 A2A 路由 |

---

## 📝 练习题

### s01 练习
1. 修改 `run_bash`，添加命令白名单模式
2. 添加一个新工具（比如 `read_file`）
3. 实现简单的错误重试机制

### s02 练习
1. 添加 `list_dir` 工具：列出目录内容
2. 添加 `search_file` 工具：搜索文件内容
3. 改进安全检查：用白名单替代黑名单

### s04 练习
1. 实现子 Agent 超时机制
2. 添加子 Agent 进度报告功能
3. 对比 OpenClaw 的 `sessions_spawn`

### s09/s10 练习
1. 添加新的消息类型（如 `help_request`）
2. 实现团队领导选举协议
3. 对比飞书 A2A 路由机制

---

## 🎯 学习路径

```
s01 (Agent Loop)
  ↓
s02 (Tool Use)
  ↓
s04 (Subagent)
  ↓
s09 (Agent Teams)
  ↓
s10 (Team Protocols)
```

建议按顺序学习，每节课都建立在前一节的基础上。

---

## 📚 参考资料

- [Anthropic API 文档](https://docs.anthropic.com/)
- [Function Calling 规范](https://docs.anthropic.com/claude/docs/tool-use)
- [ReAct 模式论文](https://arxiv.org/abs/2210.03629)
- [OpenClaw 项目](https://github.com/openclaw/openclaw)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 License

MIT

---

## ⏳ 待补充内容

以下模块的注解版本待补充：

### s03-s11：注解版待补充
**状态：** 所有代码和笔记已完成，注解版（`*_annotated.py`）原仓库只有 s01/s02 有提供

### s12：工作树隔离 (Worktree Isolation)
**状态：** 原仓库不存在此文件，可能已移除或合并到其他模块
