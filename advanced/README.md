# Advanced - 进阶课程：从学习到生产

> 融合 Cat Café Tutorials 的生产教训，构建真正可用的 Agent 系统

---

## 📚 课程列表

| 课 | 主题 | 融合内容 | 产出 |
|----|------|----------|------|
| **adv01** | A2A 路由与深度限制 | Cat Café 第 4 课 + s04 子智能体 | 带深度检查的路由器 |
| **adv02** | Session 管理与上下文链 | Cat Café 第 8 课 + s06 上下文压缩 | Session Chain Manager |
| **adv03** | 冷启动验证器 | Cat Café 第 9 课 + s09 智能体团队 | Cold Start Verifier Skill |
| **adv04** | 知识管理与三层记忆 | Cat Café 第 10 课 + s05 Skills | Knowledge Curator Skill |
| **adv05** | 生产安全护栏 | Cat Café 第 2/6 课 + s10 团队协议 | 7 个护栏脚本 |
| **adv06** | MCP 回传与主动通知 | Cat Café 第 5 课 + s08 后台任务 | MCP 通知系统 |
| **adv07** | 从工具到平台 | Cat Café 第 7 课 + s11 自治智能体 | Rich Blocks + PWA |
| **adv08** | 降级与容错 | Cat Café 第 11 课 + s12 Worktree 隔离 | 容错架构设计 |

---

## 🎯 适合人群

- ✅ 已完成 s01-s12 基础课程
- ✅ 想构建生产级 Agent 系统
- ✅ 对多 Agent 协作感兴趣
- ✅ 想避开生产事故的坑

---

## 🚀 快速开始

```bash
cd advanced

# 从第一课开始
python examples/adv01_a2a_router.py

# 运行护栏检查
node ../../scripts/check-frontmatter.mjs
node ../../scripts/check-dir-size.mjs
```

---

## 📖 与基础课程的关系

```
基础课程 (s01-s12)          进阶课程 (adv01-adv08)
==================          ======================
s04 子智能体         ────→   adv01 A2A 路由 + 深度限制
s06 上下文压缩       ────→   adv02 Session 管理
s09 智能体团队       ────→   adv03 冷启动验证
s05 Skills           ────→   adv04 知识管理
s10 团队协议         ────→   adv05 生产安全
s08 后台任务         ────→   adv06 MCP 回传
s11 自治智能体       ────→   adv07 平台化
s12 Worktree 隔离    ────→   adv08 降级容错
```

---

## 🏆 认证体系

完成进阶课程后可获得：

| 证书 | 要求 | 权益 |
|------|------|------|
| 🐱 **见习铲屎官** | 完成 adv01-adv03 | 访问私有 Discord |
| 🐱🐱 **资深铲屎官** | 完成 adv04-adv06 + 1 个项目 | 参与 Code Review |
| 🐱🐱🐱 **猫咖大师** | 完成 adv07-adv08 + Capstone | 联合署名教程 |

---

## 📁 项目结构

```
advanced/
├── README.md                 # 本文件
├── PROGRESS.md               # 开发进度
├── docs/                     # 详细文档
│   ├── adv01-a2a-routing.md
│   ├── adv02-session-chain.md
│   ├── adv03-cold-start-verifier.md
│   ├── adv04-knowledge-curator.md
│   ├── adv05-production-guards.md
│   ├── adv06-mcp-callbacks.md
│   ├── adv07-platform.md
│   └── adv08-fault-tolerance.md
├── examples/                 # 代码示例
│   ├── adv01_a2a_router.py
│   ├── adv02_session_chain.py
│   ├── adv03_cold_start_verifier.py
│   └── ...
└── capstone/                 # 毕业设计
    └── project-brief.md
```

---

## 🔗 相关资源

- [Cat Café Tutorials](https://github.com/zts212653/cat-cafe-tutorials)
- [learn-claude-code 基础课程](../README-zh.md)
- [A2A Router 实现](../../a2a-router/README.md)
- [Skill 系统](../../skills/)

---

**从理解原理，到构建生产系统。**
