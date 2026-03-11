# 修改 learn-claude-code 使用阿里 CodingPlan API

## ✅ 已完成修改

| 模块 | 原始文件 | OpenAI 版本 | 状态 |
|------|---------|-----------|------|
| s01 | s01_agent_loop.py | s01_agent_loop_openai.py | ✅ 完成 |
| s02 | s02_tool_use.py | s02_tool_use_openai.py | ✅ 完成 |
| s03 | s03_todo_write.py | s03_todo_write_openai.py | ✅ 完成 |
| s04 | s04_subagent.py | ⏳ 待创建 | ⏳ 进行中 |
| s05-s11 | ... | ⏳ 待创建 | ⏳ 待开始 |

## 📋 修改清单

### 1. 安装依赖

```bash
pip install openai python-dotenv
```

### 2. 创建 `.env` 文件

```bash
# 阿里 CodingPlan API 配置
DASHSCOPE_API_KEY=your_api_key_here
MODEL_ID=qwen-coder-plus
```

### 3. 修改代码

所有 `.py` 文件需要做以下修改：

#### 修改前（Anthropic SDK）
```python
from anthropic import Anthropic

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

response = client.messages.create(
    model=MODEL,
    system=SYSTEM,
    messages=messages,
    tools=TOOLS,
    max_tokens=8000,
)
```

#### 修改后（OpenAI SDK - 兼容阿里 CodingPlan）
```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.environ["MODEL_ID"]

response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "system", "content": SYSTEM}] + messages,
    tools=TOOLS,
    max_tokens=8000,
)
```

### 4. 工具调用响应格式差异

#### Anthropic 格式
```python
# 响应结构
response.content  # [Block(...), Block(...)]
block.type == "tool_use"
block.id
block.name
block.input

# 停止原因
response.stop_reason == "tool_use"
```

#### OpenAI/阿里格式
```python
# 响应结构
response.choices[0].message  # Message 对象
message.tool_calls  # [ToolCall(...), ...]
tool_call.id
tool_call.function.name
tool_call.function.arguments

# 判断是否有工具调用
if message.tool_calls:
    # 有工具调用
```

### 5. 完整修改示例

参考 `s01_agent_loop_openai.py` - 这是修改后的完整示例

## 🔍 关键差异

| 项目 | Anthropic | OpenAI/阿里 |
|------|-----------|-------------|
| SDK | `anthropic` | `openai` |
| API Key | `ANTHROPIC_API_KEY` | `DASHSCOPE_API_KEY` |
| 端点 | `anthropic.com` | `dashscope.aliyuncs.com` |
| 消息格式 | `messages=[...]` | `messages=[{"role": "system", ...}] + messages` |
| 工具调用 | `response.content` | `response.choices[0].message.tool_calls` |
| 工具结果 | `tool_result` | `tool_result`（相同） |

## 📝 注意事项

1. **系统提示词**：OpenAI 格式需要把 system 放在 messages 数组里
2. **工具调用**：响应结构不同，需要解析 `tool_calls` 而不是 `content`
3. **工具结果**：格式基本相同，但 `tool_call_id` 代替了 `tool_use_id`
4. **模型能力**：Qwen Coder 可能不支持所有 Claude 的功能

## ✅ 修改步骤

1. 复制 `s01_agent_loop_openai.py` 到所有模块
2. 修改 `.env` 文件配置 API Key
3. 运行测试：`python s01_agent_loop_openai.py`
4. 根据测试结果调整工具和提示词

## 🔗 参考文档

- 阿里 DashScope 文档：https://help.aliyun.com/zh/dashscope/
- OpenAI 兼容模式：https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope/
