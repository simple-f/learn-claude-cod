# 第 4 课：流式输出

> 打字机效果的流式输出实现

---

## 📖 学习目标

完成本课后，你将能够：

- ✅ 理解 SSE（Server-Sent Events）原理
- ✅ 实现流式输出
- ✅ 优化用户体验
- ✅ 处理流式错误

**预计时间：** 2-3 小时

---

## 🎯 一、为什么需要流式输出？

### 1.1 对比：非流式 vs 流式

**非流式输出：**
```
用户提问 → 等待 3 秒 → 一次性显示完整答案
👤 你：怎么退货？
🤖 客服：[等待 3 秒...] 您好，退货流程如下：1. 登录账户...
```

**流式输出：**
```
用户提问 → 立即显示 → 逐字输出
👤 你：怎么退货？
🤖 客服：您→好→，→退→货→流→程→如→下→：→1→.→...
```

**用户体验提升：**
- ✅ 减少等待焦虑
- ✅ 更自然（像真人打字）
- ✅ 可提前阅读

### 1.2 流式输出方案

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **SSE** | 简单、单向 | 仅文本 | 客服/聊天 |
| **WebSocket** | 双向、实时 | 复杂 | 实时协作 |
| **HTTP Chunk** | 简单 | 兼容性差 | 文件下载 |

---

## 💻 二、核心代码详解

### 2.1 SSE 原理

**SSE（Server-Sent Events）** 是 HTML5 标准，允许服务器向浏览器推送实时更新。

```javascript
// 前端代码
const eventSource = new EventSource('/api/chat');

eventSource.onmessage = (event) => {
    console.log('收到消息:', event.data);
    // 追加到聊天界面
};
```

**后端代码（Python）：**

```python
# src/stream/output.py
from fastapi.responses import StreamingResponse
import asyncio

async def stream_generator(text: str):
    """SSE 流生成器"""
    for char in text:
        yield f"data: {char}\n\n"
        await asyncio.sleep(0.1)  # 打字延迟

@app.get("/api/chat")
async def chat():
    return StreamingResponse(
        stream_generator("您好，有什么可以帮助您的？"),
        media_type="text/event-stream"
    )
```

### 2.2 流式输出器

```python
# src/stream/output.py
class StreamingOutput:
    def __init__(self, config):
        self.config = config
        self.delay = config.stream_delay / 1000.0  # 转换为秒
    
    async def stream(self, text: str):
        """流式输出文本"""
        for char in text:
            yield char
            await asyncio.sleep(self.delay)
    
    async def stream_words(self, text: str):
        """按词流式输出"""
        words = text.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word
            await asyncio.sleep(self.delay * 3)
    
    async def stream_lines(self, text: str):
        """按行流式输出"""
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                yield '\n'
            yield line
            await asyncio.sleep(self.delay * 5)
```

**流式策略对比：**

| 策略 | 延迟 | 流畅度 | 适用场景 |
|------|------|--------|----------|
| **按字** | 100ms | 最好 | 中文 |
| **按词** | 300ms | 好 | 英文 |
| **按行** | 500ms | 一般 | 长文本 |

### 2.3 集成到 Agent

```python
# src/agent.py
async def chat(self, user_id: str, message: str) -> str:
    """处理用户对话（流式版本）"""
    # ... 前面的逻辑不变
    
    # 调用 LLM
    answer = await self._generate_answer(prompt)
    
    # 流式输出
    print("🤖 客服：", end="", flush=True)
    async for chunk in self.output.stream(answer):
        print(chunk, end="", flush=True)
    print()
    
    return answer
```

---

## 🌐 三、Web 集成

### 3.1 FastAPI 后端

```python
# src/web_server.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/api/chat/stream")
async def chat_stream(request: dict):
    """流式聊天接口"""
    user_id = request.get("user_id", "default")
    message = request.get("message", "")
    
    async def generate():
        answer = await agent.chat(user_id, message)
        for char in answer:
            yield f"data: {json.dumps({'text': char})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 3.2 前端代码

```html
<!-- frontend/streaming.html -->
<!DOCTYPE html>
<html>
<head>
    <title>智能客服 - 流式输出</title>
</head>
<body>
    <div id="chat"></div>
    <input id="input" placeholder="输入问题...">
    <button onclick="send()">发送</button>

    <script>
        async function send() {
            const input = document.getElementById('input');
            const message = input.value;
            input.value = '';

            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message})
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;

                const text = decoder.decode(value);
                const lines = text.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        document.getElementById('chat').innerText += data.text;
                    }
                }
            }
        }
    </script>
</body>
</html>
```

---

## 📊 四、性能优化

### 4.1 延迟优化

**问题：** 逐字输出太慢

**解决方案：**
```python
# 动态延迟
async def stream_smart(self, text: str):
    """智能流式输出"""
    # 标点符号延迟短
    punctuation = '，。！？、；："'
    
    for char in text:
        yield char
        if char in punctuation:
            await asyncio.sleep(self.delay * 2)  # 标点停顿
        else:
            await asyncio.sleep(self.delay)
```

### 4.2 错误处理

```python
# src/stream/output.py
async def stream_with_error_handling(self, text: str):
    """带错误处理的流式输出"""
    try:
        async for chunk in self.stream(text):
            yield chunk
    except asyncio.CancelledError:
        print("\n⚠️  用户取消了输出")
        yield "[已取消]"
    except Exception as e:
        print(f"\n❌ 流式输出错误：{e}")
        yield "[输出错误]"
```

---

## ✅ 五、动手实践

### 5.1 练习 1：测试流式输出

```python
# 运行测试
python -c "
import asyncio
from src.stream.output import StreamingOutput
from src.config import Config

config = Config.load()
output = StreamingOutput(config)

async def test():
    text = '您好，感谢您的咨询。关于您的问题，我会尽快为您解答。'
    async for chunk in output.stream(text):
        print(chunk, end='', flush=True)

asyncio.run(test())
"
```

### 5.2 练习 2：调整延迟

```python
# 修改 .env
# 尝试不同的延迟值

STREAM_DELAY=50    # 快速
STREAM_DELAY=100   # 正常
STREAM_DELAY=200   # 慢速

# 对比效果
```

### 5.3 练习 3：Web 界面测试

```bash
# 启动 Web 服务器
python src/web_server.py

# 访问 http://localhost:8000
# 测试流式聊天
```

---

## 📝 六、课后作业

### 必做题

1. **理解 SSE 原理**
   - 画出 SSE 通信流程图
   - 对比 WebSocket

2. **测试流式输出**
   - 用 3 种延迟测试
   - 记录用户体验

3. **集成到 Agent**
   - 修改 agent.py
   - 实现流式输出

### 选做题

1. **实现智能延迟**
   - 标点符号停顿
   - 段落停顿

2. **添加取消功能**
   - 用户可中断输出
   - 清理资源

3. **性能优化**
   - 测量首字延迟
   - 优化输出速度

---

## 📚 七、参考资料

### 7.1 SSE 规范

- [MDN SSE 文档](https://developer.mozilla.org/zh-CN/docs/Web/API/Server-sent_events)
- [HTML5 SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)

### 7.2 FastAPI

- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)

### 7.3 用户体验

- [打字机效果最佳实践](https://www.nngroup.com/articles/response-times-3-important-limits/)
- [聊天界面设计](https://www.smashingmagazine.com/2020/07/designing-chat-interfaces/)

---

## 🎯 八、下节预告

**第 5 课：意图识别**

- ✅ 规则匹配
- ✅ 分类模型
- ✅ 意图跳转
- ✅ 混淆处理

**前置知识：**
- 理解流式输出
- 完成本课实践
- 测试过 SSE

---

**持续更新中...**

_最后更新：2026-03-12_

_作者：付艺锦 + ai2 (claw 后端机器人)_
