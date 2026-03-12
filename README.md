# Learn Claude Code -- 从 0 到 1 构建 AI Agent

> **12 节渐进式课程，从简单循环到完整的多 Agent 协作系统**

[English](./README.md) | [中文](./README-zh.md) | [日本語](./README-ja.md)

---

## 🎯 核心模式

```
                    THE AGENT PATTERN
                    =================

    User --> messages[] --> LLM --> response
                                      |
                            stop_reason == "tool_use"?
                           /                          \
                         yes                           no
                          |                             |
                    execute tools                    return text
                    append results
                    loop back -----------------> messages[]


这是最小循环。每个 AI 编程 Agent 都需要这个循环。
生产级 Agent 还会叠加策略、权限与生命周期层。
```

**12 个渐进式课程，从简单循环到隔离化的自治执行。**

每个课程添加一个机制，每个机制有一句格言：

> **s01** *"One loop & Bash is all you need"* — 一个工具 + 一个循环 = 一个智能体
>
> **s02** *"Adding a tool means adding one handler"* — 循环不变，新工具注册进 dispatch map
>
> **s03** *"An agent without a plan drifts"* — 先列步骤再执行，完成率翻倍
>
> **s04** *"Break big tasks down; each subtask gets a clean context"* — 子智能体用独立 messages[]
>
> **s05** *"Load knowledge when you need it, not upfront"* — 通过 tool_result 注入，不塞 system prompt
>
> **s06** *"Context will fill up; you need a way to make room"* — 三层压缩策略，无限会话
>
> **s07** *"Break big goals into small tasks, order them, persist to disk"* — 文件持久化任务图
>
> **s08** *"Run slow operations in the background; the agent keeps thinking"* — 后台线程 + 通知队列
>
> **s09** *"When the task is too big for one, delegate to teammates"* — 持久化队友 + JSONL 信箱
>
> **s10** *"Teammates need shared communication rules"* — 统一 request-response 协议
>
> **s11** *"Teammates scan the board and claim tasks themselves"* — 空闲轮询 + 自动认领
>
> **s12** *"Each works in its own directory, no interference"* — 任务管目标，worktree 管目录

---

## 📚 课程目录

### 阶段 1：核心循环（第 1-2 天）

| 课程 | 主题 | 格言 | 代码 | 笔记 |
|------|------|------|------|------|
| **s01** | [Agent 循环](./docs/en/s01-the-agent-loop.md) | One loop & Bash is all you need | [s01_agent_loop.py](./agents/s01_agent_loop.py) | [笔记](./s01_notes.md) |
| **s02** | [工具系统](./docs/en/s02-tool-use.md) | 加一个工具，只加一个 handler | [s02_tool_use.py](./agents/s02_tool_use.py) | [笔记](./s02_notes.md) |

### 阶段 2：规划与知识（第 3-5 天）

| 课程 | 主题 | 格言 | 代码 | 笔记 |
|------|------|------|------|------|
| **s03** | [任务规划](./docs/en/s03-todo-write.md) | 没有计划的 agent 走哪算哪 | [s03_todo_write.py](./agents/s03_todo_write.py) | [笔记](./s03_notes.md) |
| **s04** | [子智能体](./docs/en/s04-subagent.md) | 大任务拆小，每个小任务干净的上下文 | [s04_subagent.py](./agents/s04_subagent.py) | [笔记](./s04_notes.md) |
| **s05** | [Skills](./docs/en/s05-skill-loading.md) | 用到什么知识，临时加载什么知识 | [s05_skill_loading.py](./agents/s05_skill_loading.py) | [笔记](./s05_notes.md) |
| **s06** | [上下文压缩](./docs/en/s06-context-compact.md) | 上下文总会满，要有办法腾地方 | [s06_context_compact.py](./agents/s06_context_compact.py) | [笔记](./s06_notes.md) |

### 阶段 3：持久化（第 6-7 天）

| 课程 | 主题 | 格言 | 代码 | 笔记 |
|------|------|------|------|------|
| **s07** | [任务系统](./docs/en/s07-task-system.md) | 大目标要拆成小任务，排好序，记在磁盘上 | [s07_task_system.py](./agents/s07_task_system.py) | [笔记](./s07_notes.md) |
| **s08** | [后台任务](./docs/en/s08-background-tasks.md) | 慢操作丢后台，agent 继续想下一步 | [s08_background_tasks.py](./agents/s08_background_tasks.py) | [笔记](./s08_notes.md) |

### 阶段 4：团队协作（第 8-10 天）

| 课程 | 主题 | 格言 | 代码 | 笔记 |
|------|------|------|------|------|
| **s09** | [智能体团队](./docs/en/s09-agent-teams.md) | 任务太大一个人干不完，要能分给队友 | [s09_agent_teams.py](./agents/s09_agent_teams.py) | [笔记](./s09_notes.md) |
| **s10** | [团队协议](./docs/en/s10-team-protocols.md) | 队友之间要有统一的沟通规矩 | [s10_team_protocols.py](./agents/s10_team_protocols.py) | [笔记](./s10_notes.md) |
| **s11** | [自治智能体](./docs/en/s11-autonomous-agents.md) | 队友自己看看板，有活就认领 | [s11_autonomous_agents.py](./agents/s11_autonomous_agents.py) | [笔记](./s11_notes.md) |
| **s12** | [Worktree 隔离](./docs/en/s12-worktree-task-isolation.md) | 各干各的目录，互不干扰 | [s12_worktree_task_isolation.py](./agents/s12_worktree_task_isolation.py) | [笔记](./s12_notes.md) |

### 毕业项目

| 课程 | 主题 | 代码 |
|------|------|------|
| **s_full** | 总纲：全部机制合一 | [s_full.py](./agents/s_full.py) |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/shareAI-lab/learn-claude-code.git
cd learn-claude-code
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 ANTHROPIC_API_KEY
```

### 4. 开始学习

```bash
# 从第一课开始
python agents/s01_agent_loop.py

# 或运行完整版本
python agents/s_full.py
```

### 5. Web 平台（可选）

交互式可视化、分步动画、源码查看器。

```bash
cd web && npm install && npm run dev
# 访问 http://localhost:3000
```

---

## 📖 文档

心智模型优先：问题、方案、ASCII 图、最小化代码。

[English](./docs/en/) | [中文](./docs/zh/) | [日本語](./docs/ja/)

### 深度技术解析（新增）

- [s01-s12 详细技术解析](./docs/s01-s12-detailed-explanations.md) - 解释关键步骤的原理和设计决策
- [学习进度追踪](./docs/PROGRESS-S01-S12.md) - s01-s12 笔记增强进度

### 实战项目

- [智能客服系统](./projects/customer-service/README.md) - 企业级 RAG 客服系统（8 课完整教程）
  - ✅ RAG 知识检索
  - ✅ Session 管理
  - ✅ 意图识别
  - ✅ 流式输出
  - ✅ 部署监控
  - ✅ LangChain 对比

---

## 📊 学习路径

```
阶段 1：核心循环                       阶段 2：规划与知识
==================                   ==============================
s01 Agent 循环 [1]                   s03 TodoWrite [5]
     while + stop_reason                  TodoManager + nag 提醒
     |                                    |
     +-> s02 Tool Use [4]               s04 子智能体 [5]
              dispatch map: name->handler   fresh messages[] per child
                                            |
                                       s05 Skills [5]
                                            SKILL.md via tool_result
                                            |
                                       s06 上下文压缩 [5]
                                            三层压缩

阶段 3：持久化                       阶段 4：团队
==================                   =====================
s07 任务系统 [8]                     s09 智能体团队 [9]
     文件持久化 CRUD + 依赖图              队友 + JSONL 信箱
     |                                    |
s08 后台任务 [6]                     s10 团队协议 [12]
     守护线程 + 通知队列                  关机 + 计划审批 FSM
                                          |
                                     s11 自治智能体 [14]
                                          空闲轮询 + 自动认领
                                          |
                                     s12 Worktree 隔离 [16]
                                          任务协调 + 隔离执行通道

[N] = 工具数量
```

---

## 🏗️ 项目结构

```
learn-claude-code/
│
├── agents/                        # Python 参考实现 (s01-s12 + s_full)
│   ├── s01_agent_loop.py
│   ├── s02_tool_use.py
│   ├── ...
│   └── s_full.py
│
├── docs/{en,zh,ja}/               # 教学文档 (3 种语言)
│
├── projects/                      # 实战项目
│   └── customer-service/          # 智能客服系统
│       ├── README.md
│       ├── docs/                  # 8 课教程
│       ├── src/                   # 源代码
│       └── tests/                 # 测试用例
│
├── web/                           # 交互式学习平台 (Next.js)
│
├── skills/                        # s05 的 Skill 文件
│
└── .github/workflows/ci.yml      # CI: 类型检查 + 构建
```

---

---

## 🔗 相关资源

### 姊妹项目

- [OpenClaw](https://github.com/openclaw/openclaw) - 常驻式 AI 助手（心跳 + 定时任务 + IM 集成）
- [claw0](https://github.com/shareAI-lab/claw0) - 从临时会话到常驻助手的教学项目

### 衍生项目

- [Kode Agent CLI](https://github.com/shareAI-lab/Kode-cli) - 开源 Coding Agent CLI
- [Kode Agent SDK](https://github.com/shareAI-lab/Kode-agent-sdk) - 嵌入式 Agent SDK

### 学习社区

- [Discord](https://discord.gg/xxx) - 学习讨论
- [GitHub Issues](https://github.com/shareAI-lab/learn-claude-code/issues) - 问题反馈

---

## 📜 许可证

MIT

---

## 💬 名言

> **"The model is the agent. Our job is to give it tools and stay out of the way."**

模型就是智能体。我们的工作就是给它工具，然后让开。

---

_最后更新：2026-03-12_
