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
| s12 | Worktree Isolation | ⏳ 只有文档 | - | ⏳ |

**当前进度：11/12 模块代码 + 11/12 模块笔记**（s12 原仓库只有文档）

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

**文件：** ⏳ 代码待补充 | `s12_notes.md`

**状态：** 原仓库只有文档，代码文件尚未创建

**推测内容：**
- Git Worktree 使用
- 任务环境隔离
- 并行任务不冲突

**参考文档：** https://github.com/shareAI-lab/learn-claude-code/blob/main/docs/en/s12-worktree-task-isolation.md

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
cd C:\Users\Administrator\.openclaw\workspace-ai1\learn-claude-code\agents
python s01_agent_loop.py
```

**示例对话：**
```
s01 >> 列出当前目录的文件
$ ls
file1.py file2.md README.md
```

### 运行第 2 课：多工具

```bash
python s02_tool_use.py
```

**支持工具：** `bash`, `read_file`, `write_file`, `edit_file`

**示例：**
```
s02 >> 创建一个测试文件
$ write_file path="test.txt" content="Hello World"
Wrote 13 bytes
```

### 运行第 3 课：任务管理

```bash
python s03_todo_write.py
```

**示例：**
```
s03 >> 创建一个任务列表
> todo items=[{"text": "分析项目", "status": "in_progress"}, {"text": "写报告", "status": "pending"}]
[>] #1: 分析项目
[ ] #2: 写报告
(0/2 completed)
```

### 运行第 4 课：子 Agent

```bash
python s04_subagent.py
```

**示例：**
```
s04 >> 用 task 工具委派一个子任务
> task (explore): 查看项目结构
  发现了 3 个 Python 文件...
```

### 运行第 5 课：技能加载

```bash
python s05_skill_loading.py
```

**示例：**
```
s05 >> 加载 PDF 处理技能
> load_skill name="pdf"
<skill name="pdf">
  Full PDF processing instructions...
</skill>
```

### 运行第 6 课：上下文压缩

```bash
python s06_context_compact.py
```

**示例：**
```
s06 >> 压缩对话历史
> compact
[transcript saved: .transcripts/transcript_1773194400.jsonl]
[Conversation compressed. Summary: ...]
```

### 运行第 7 课：任务系统

```bash
python s07_task_system.py
```

**示例：**
```
s07 >> 创建依赖任务
> task_create subject="设计数据库" description="设计用户表"
> task_create subject="实现 API" blocked_by=[1]
[ ] #1: 设计数据库
[ ] #2: 实现 API (blocked by: [1])
```

### 运行第 8 课：后台任务

```bash
python s08_background_tasks.py
```

**示例：**
```
s08 >> 后台运行耗时命令
> background_run command="sleep 10 && echo Done"
Background task abc123 started: sleep 10 && echo Done
> background_check
abc123: [completed] sleep 10 && echo Done
```

### 运行第 9 课：团队协作

```bash
python s09_agent_teams.py
```

**示例：**
```
s09 >> 创建队友
> spawn_teammate name="alice" role="coder"
> send_message to="alice" content="修复登录 bug"
Sent message to alice
```

### 运行第 10 课：团队协议

```bash
python s10_team_protocols.py
```

**示例：**
```
s10 >> 请求关闭队友
> request_shutdown requester="lead" target="alice"
Shutdown requested: abc123 -> alice
```

### 运行第 11 课：自主 Agent

```bash
python s11_autonomous_agents.py
```

**示例：**
```
s11 >> 创建自主队友
> spawn_autonomous name="bob" role="worker"
[Bob] claimed task #3
[Bob] working...
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
4. **对比 OpenClaw**：我们的 bash 工具和 OpenClaw 的 exec 有什么区别？

### s02 练习
1. 添加 `list_dir` 工具：列出目录内容
2. 添加 `search_file` 工具：搜索文件内容
3. 改进安全检查：用白名单替代黑名单
4. **对比 OpenClaw**：我们的 TOOL_HANDLERS 和 OpenClaw 的 Skills 系统有什么区别？

### s03 练习
1. 添加优先级字段：`priority`（high/medium/low）
2. 添加子任务：支持嵌套 todo（`parent_id` 字段）
3. 添加截止日期：`due_date` 字段，超期提醒
4. **对比 OpenClaw**：我们的 TodoManager 和 HEARTBEAT.md 有什么区别？

### s04 练习
1. 实现子 Agent 超时机制（60 秒自动终止）
2. 添加子 Agent 进度报告功能
3. 实现并行派生（同时派生 3 个子 Agent）
4. **对比 OpenClaw**：我们的 `run_subagent` 和 `sessions_spawn` 有什么区别？

### s05 练习
1. 添加技能搜索：实现 `search_skill(keyword)` 工具
2. 添加技能缓存：加载过的技能缓存在内存
3. 添加技能依赖：技能 A 依赖技能 B（自动加载）
4. **对比 OpenClaw**：找一个 OpenClaw skill，分析它和 s05 的区别

### s06 练习
1. 添加手动压缩工具：让 LLM 可以主动调用 `compact()`
2. 改进总结提示词：添加更多总结维度（如"遇到的问题"）
3. 添加压缩历史：记录每次压缩的时间和原因
4. **对比 OpenClaw**：我们的 session 管理和 s06 有什么区别？

### s07 练习
1. 添加任务优先级：`priority` 字段（high/medium/low）
2. 添加任务标签：`tags` 字段（如 `["backend", "urgent"]`）
3. 添加截止日期：`due_date` 字段，超期提醒
4. 实现任务看板：按状态分组显示任务

### s08 练习
1. 添加进度报告：后台任务定期更新进度
2. 添加取消功能：`cancel(task_id)` 终止任务
3. 添加重试机制：失败的任务自动重试
4. **对比 OpenClaw**：我们的后台任务和 OpenClaw 的 sessions_spawn 有什么区别？

### s09 练习
1. 添加消息优先级：urgent/normal/low，优先处理 urgent
2. 实现消息确认：接收方回复 ACK，发送方知道消息已读
3. 添加群聊支持：一个消息发送给多个队友（群组）
4. **对比 OpenClaw**：我们的飞书消息和 s09 有什么区别？

### s10 练习
1. 添加超时机制：请求超过 60 秒无响应自动拒绝
2. 实现强制关闭：Lead 可以强制关闭不响应的队友
3. 添加计划模板：预定义计划格式（如"探索型"、"执行型"）
4. **对比 OpenClaw**：我们的 A2A 协作有没有类似的协议？

### s11 练习
1. 添加任务优先级：优先认领高优先级任务
2. 添加技能匹配：只认领自己擅长类型的任务
3. 添加协作认领：多个 Agent 合作完成大任务
4. **对比 OpenClaw**：我们的 HEARTBEAT 和 s11 空闲循环有什么区别？

---

## 🎯 学习路径

### 阶段一：核心循环（第 1-2 天）

```
s01 (Agent Loop) → s02 (Tool Use)
```

**学习目标：**
- 理解 ReAct 模式（Reason + Act）
- 理解工具调用流程
- 能手绘 Agent 循环流程图

### 阶段二：规划与知识（第 3-5 天）

```
s03 (Todo Write) → s04 (Subagent) → s05 (Skill Loading) → s06 (Context Compact)
```

**学习目标：**
- 理解任务分解策略
- 理解子代理通信机制
- 对比 OpenClaw 的 A2A 协作

### 阶段三：持久化（第 6-7 天）

```
s07 (Task System) → s08 (Background Tasks)
```

**学习目标：**
- 理解任务持久化
- 理解定时任务调度
- 对比我们的 Cron/Heartbeat

### 阶段四：团队协作（第 8-10 天）

```
s09 (Agent Teams) → s10 (Team Protocols) → s11 (Autonomous Agents)
```

**学习目标：**
- 理解多 Agent 协作模式
- 理解任务隔离策略
- 能设计自己的 Agent 团队

### 推荐流程（每模块）

1. **读文档**（笔记文件） - 10 分钟
2. **读代码**（`.py` 文件） - 20 分钟
3. **运行示例** - 10 分钟
4. **动手改** - 30 分钟（改代码、加功能）
5. **对比 OpenClaw** - 15 分钟（找异同）

**单模块耗时：** 约 1.5-2 小时

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

### 注解版本

**状态：** 原仓库只提供了 s01/s02 的注解版（`*_annotated.py`）

**本地进度：**
- ✅ s01_agent_loop_annotated.py（原仓库提供）
- ✅ s02_tool_use_annotated.py（原仓库提供）
- ✅ s03_todo_write_annotated.py（已创建）
- ✅ s04_subagent_annotated.py（已创建）
- ⏳ s05-s11 注解版待创建

### s12 模块

**状态：** 原仓库只有文档，代码文件尚未实现

**文档：** https://github.com/shareAI-lab/learn-claude-code/blob/main/docs/en/s12-worktree-task-isolation.md

**推测内容：**
- Git Worktree 多工作区隔离
- 每个任务独立的工作区
- 避免文件冲突

---
