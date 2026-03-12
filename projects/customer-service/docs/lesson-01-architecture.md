# 第 1 课：项目架构设计

> 理解智能客服系统的整体架构

---

## 📖 学习目标

完成本课后，你将能够：

- ✅ 理解智能客服系统的核心组件
- ✅ 掌握 RAG 系统的工作原理
- ✅ 设计多轮对话的 Session 管理
- ✅ 搭建完整的项目结构

**预计时间：** 2-3 小时

---

## 🎯 一、需求分析

### 1.1 业务场景

**场景：** 电商公司的客服部门每天要处理 1000+ 个用户咨询

**常见问题：**
```
用户：我的订单什么时候发货？
用户：我想退货，怎么操作？
用户：发票能开专票吗？
用户：这个商品有优惠吗？
```

**痛点：**
- ❌ 人工客服响应慢（平均 5 分钟）
- ❌ 重复问题多（80% 是常见问题）
- ❌ 夜间无人值班
- ❌ 培训成本高

### 1.2 解决方案

**智能客服系统：**
```
┌─────────────────────────────────────────────────────────┐
│                    智能客服系统                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  用户提问 → 意图识别 → 知识检索 → 答案生成 → 输出答案   │
│      │           │           │            │            │
│      ▼           ▼           ▼            ▼            │
│  多轮对话    分类模型    向量数据库    LLM 生成     流式输出  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**预期效果：**
- ✅ 响应时间 < 2 秒
- ✅ 准确率 > 85%
- ✅ 7x24 小时在线
- ✅ 自动学习新知识

---

## 🏗️ 二、架构设计

### 2.1 核心组件

```
┌──────────────────────────────────────────────────────────┐
│                      智能客服架构                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐                                        │
│  │  用户界面   │  Web/APP/微信/电话                     │
│  └──────┬──────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐     ┌─────────────┐                    │
│  │  意图识别   │────▶│  Session 管理 │                    │
│  └──────┬──────┘     └──────┬──────┘                    │
│         │                   │                            │
│         ▼                   ▼                            │
│  ┌─────────────┐     ┌─────────────┐                    │
│  │  知识检索   │◀────│  上下文管理  │                    │
│  │   (RAG)     │     │             │                    │
│  └──────┬──────┘     └─────────────┘                    │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  答案生成   │  LLM (OpenAI/Claude/GLM)               │
│  └──────┬──────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  流式输出   │  SSE/WebSocket                         │
│  └─────────────┘                                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 2.2 数据流

**一次完整的对话流程：**

```python
# 伪代码示例
user_input = "我的订单什么时候发货？"

# 1. 意图识别
intent = recognize_intent(user_input)  # 输出："shipping_query"

# 2. 加载会话历史
session = get_session(user_id="user_123")
history = session.get_history()

# 3. 知识检索
if intent == "shipping_query":
    knowledge = rag_retrieve(user_input, top_k=3)
else:
    knowledge = []

# 4. 构建提示词
prompt = build_prompt(user_input, history, knowledge)

# 5. 调用 LLM
answer = llm.generate(prompt)

# 6. 流式输出
for chunk in stream_output(answer):
    print(chunk, end="", flush=True)

# 7. 保存会话
session.add_message("user", user_input)
session.add_message("assistant", answer)
```

---

## 📁 三、项目结构

### 3.1 目录结构

```
customer-service/
├── README.md                 # 项目说明
├── requirements.txt          # Python 依赖
├── .env.example            # 环境变量模板
│
├── src/                     # 源代码
│   ├── main.py             # 主入口
│   ├── agent.py            # 客服 Agent
│   ├── web_server.py       # Web 服务器
│   │
│   ├── rag/                # RAG 模块
│   │   ├── embedder.py     # Embedding 向量化
│   │   ├── retriever.py    # 检索器
│   │   └── vector_db.py    # 向量数据库
│   │
│   ├── session/            # Session 管理
│   │   ├── manager.py      # 会话管理器
│   │   └── compressor.py   # 上下文压缩
│   │
│   ├── intent/             # 意图识别
│   │   ├── rule_matcher.py # 规则匹配
│   │   └── classifier.py   # 分类模型
│   │
│   ├── stream/             # 流式输出
│   │   └── output.py       # SSE 输出
│   │
│   └── monitor/            # 监控
│       └── metrics.py      # 指标收集
│
├── docs/                    # 文档
│   ├── lesson-01-architecture.md
│   ├── lesson-02-rag-design.md
│   └── ...
│
├── tests/                   # 测试
│   ├── test_rag.py
│   ├── test_session.py
│   └── ...
│
└── data/                    # 数据
    ├── knowledge/          # 知识库
    ├── vector_db/          # 向量数据库
    └── logs/               # 日志
```

### 3.2 核心文件说明

| 文件 | 作用 | 代码量 |
|------|------|--------|
| `src/main.py` | 主入口，命令行运行 | 50 行 |
| `src/agent.py` | 客服 Agent 核心逻辑 | 150 行 |
| `src/rag/retriever.py` | RAG 检索器 | 100 行 |
| `src/session/manager.py` | Session 管理器 | 120 行 |
| `src/stream/output.py` | 流式输出 | 80 行 |

---

## 💻 四、环境搭建

### 4.1 系统要求

| 要求 | 最低配置 | 推荐配置 |
|------|----------|----------|
| **操作系统** | Windows 10 / macOS 11 / Linux | Windows 11 / macOS 12 |
| **Python** | 3.9+ | 3.11+ |
| **内存** | 4GB | 8GB+ |
| **磁盘** | 1GB | 5GB+ |

### 4.2 安装步骤

**步骤 1：克隆项目**

```bash
# 进入项目目录
cd C:\Users\Administrator\.openclaw\workspace-ai2\shared\learn-claude-code-clean\projects\customer-service

# 确认项目结构
ls -R
```

**步骤 2：创建虚拟环境**

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 激活虚拟环境（macOS/Linux）
source venv/bin/activate

# 验证激活成功
python --version  # 应该显示虚拟环境的 Python 版本
```

**步骤 3：安装依赖**

```bash
# 安装 Python 包
pip install -r requirements.txt

# 验证安装
pip list | grep -E "openai|faiss|sentence-transformers"
```

**步骤 4：配置环境变量**

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
# Windows: 用记事本打开
# macOS/Linux: vim .env

# 填入你的 API Key
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
VECTOR_DB_PATH=./data/vector_db
LOG_LEVEL=INFO
```

**步骤 5：准备知识库**

```bash
# 创建知识库目录
mkdir -p data/knowledge

# 放入 FAQ 文档
# 将你的 FAQ.txt 放入 data/knowledge/ 目录
```

**步骤 6：测试运行**

```bash
# 运行主程序
python src/main.py

# 应该看到：
# ✅ 系统初始化成功
# 🤖 客服助手已就绪
# 输入你的问题（输入 quit 退出）：
```

---

## 🔍 五、核心概念详解

### 5.1 RAG（检索增强生成）

**什么是 RAG？**

```
传统 LLM：
用户问题 → LLM → 答案
         (可能胡说八道)

RAG 增强：
用户问题 → 检索知识库 → 相关知识 + 问题 → LLM → 答案
         (基于事实)      (有据可依)
```

**RAG 工作流程：**

```python
# 1. 文档预处理
documents = load_documents("data/knowledge/")
chunks = split_documents(documents)  # 切片

# 2. 向量化
embeddings = embedder.encode(chunks)

# 3. 存储到向量数据库
vector_db.add(chunks, embeddings)

# 4. 检索
query = "我的订单什么时候发货？"
query_embedding = embedder.encode(query)
results = vector_db.search(query_embedding, top_k=3)

# 5. 生成答案
prompt = f"""
基于以下知识回答问题：
{results}

问题：{query}
"""
answer = llm.generate(prompt)
```

### 5.2 Session 管理

**为什么需要 Session？**

```
用户：我想退货
客服：好的，请问订单号是多少？
用户：123456
客服：已收到，退货原因是？
用户：质量不好
     ↑
这里需要记住前面的对话！
```

**Session 实现：**

```python
class Session:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.messages = []  # 对话历史
    
    def add_message(self, role: str, content: str):
        """添加消息"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })
    
    def get_history(self, last_n: int = 10) -> List[Dict]:
        """获取最近 N 条对话"""
        return self.messages[-last_n:]
    
    def clear(self):
        """清空会话"""
        self.messages = []
```

### 5.3 流式输出

**什么是流式输出？**

```
非流式：
用户等待 3 秒 → 一次性显示完整答案

流式：
用户立即看到 → "您" → "您好" → "您好，我" → "您好，我来" → ...
              (打字机效果)
```

**流式实现：**

```python
async def stream_output(answer: str):
    """流式输出"""
    words = answer.split()
    for word in words:
        print(word, end=" ", flush=True)
        await asyncio.sleep(0.1)  # 模拟打字延迟
```

---

## ✅ 六、动手实践

### 6.1 练习 1：运行示例代码

```bash
# 运行主程序
python src/main.py

# 测试对话
> 你好
> 我想退货
> 订单号是多少
> quit
```

### 6.2 练习 2：添加自定义 FAQ

```bash
# 1. 创建 FAQ 文件
echo "Q: 怎么修改密码？
A: 登录账户后，进入设置页面，点击修改密码。" > data/knowledge/custom_faq.txt

# 2. 重新索引
python src/rag/indexer.py

# 3. 测试
python src/main.py
> 怎么修改密码？
```

### 6.3 练习 3：查看日志

```bash
# 查看运行日志
cat data/logs/app.log

# 实时监控日志
tail -f data/logs/app.log
```

---

## 📝 七、课后作业

### 必做题

1. **搭建环境**
   - 完成所有安装步骤
   - 成功运行主程序
   - 截图提交

2. **理解架构**
   - 画出系统架构图
   - 标注每个组件的作用
   - 用自己的话解释 RAG 原理

3. **修改配置**
   - 修改 `.env` 中的配置
   - 调整日志级别为 DEBUG
   - 观察日志输出变化

### 选做题

1. **添加新功能**
   - 实现一个简单的意图识别规则
   - 添加一个新的 FAQ 类别

2. **性能优化**
   - 测量响应时间
   - 找出性能瓶颈
   - 提出优化建议

---

## 📚 八、参考资料

### 8.1 必读

- [RAG 原理论文](https://arxiv.org/abs/2005.11401)
- [Session 管理最佳实践](https://docs.langchain.com/docs/components/memory)

### 8.2 选读

- [FAISS 向量数据库文档](https://github.com/facebookresearch/faiss)
- [SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)

### 8.3 工具

- [OpenAI API 文档](https://platform.openai.com/docs)
- [Sentence Transformers](https://www.sbert.net/)

---

## 🎯 九、下节预告

**第 2 课：RAG 系统实现**

- ✅ 向量数据库选型（FAISS vs Pinecone）
- ✅ 文档切片策略
- ✅ Embedding 模型选择
- ✅ 检索优化技巧

**前置知识：**
- 理解本课的架构图
- 完成环境搭建
- 运行过示例代码

---

**持续更新中...**

_最后更新：2026-03-12_

_作者：付艺锦 + ai2 (claw 后端机器人)_
