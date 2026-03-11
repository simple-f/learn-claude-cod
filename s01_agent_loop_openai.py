#!/usr/bin/env python3
"""
s01_agent_loop_openai.py - The Agent Loop (OpenAI/阿里 CodingPlan 兼容版)

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 兼容阿里 CodingPlan API (DashScope)
- 支持 Qwen Coder 系列模型

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s01_agent_loop_openai.py
"""

import os
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件配置
load_dotenv(override=True)

# 初始化 OpenAI 客户端（兼容阿里 DashScope）
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.environ.get("MODEL_ID", "qwen-coder-plus")

# 系统提示词
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# 工具定义（OpenAI 格式）
TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute."
                }
            },
            "required": ["command"]
        }
    }
}]


def run_bash(command: str) -> str:
    """
    执行 bash 命令并返回输出
    
    安全检查：
    - 危险命令黑名单（rm -rf /, sudo, shutdown, reboot）
    - 超时限制：120 秒
    - 输出截断：最多 50000 字符
    """
    # 危险命令黑名单
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    
    try:
        r = subprocess.run(
            command, 
            shell=True, 
            cwd=os.getcwd(),
            capture_output=True, 
            text=True, 
            timeout=120
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def agent_loop(messages: list):
    """
    Agent 核心循环
    
    【OpenAI 格式 vs Anthropic 格式】
    
    Anthropic:
    - response.content -> [Block(...)]
    - block.type == "tool_use"
    - block.input -> dict
    
    OpenAI:
    - response.choices[0].message.tool_calls -> [ToolCall(...)]
    - tool_call.function.name -> str
    - tool_call.function.arguments -> JSON string
    
    【关键差异】
    1. 系统提示词：OpenAI 需要放在 messages 数组里
    2. 工具调用：解析 tool_calls 而不是 content
    3. 工具结果：tool_call_id 代替 tool_use_id
    """
    while True:
        # 调用 LLM（OpenAI 格式）
        # 注意：system 需要放在 messages 数组里
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        
        # 获取助手消息
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        # 检查是否有工具调用
        # OpenAI 格式：tool_calls 列表
        if not assistant_message.tool_calls:
            # 没有工具调用，结束
            return
        
        # 执行工具调用
        results = []
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            print(f"\033[33m$ {function_args}\033[0m")
            
            # 调用对应的函数
            if function_name == "bash":
                import json
                args = json.loads(function_args)
                output = run_bash(args["command"])
                print(output[:200])
                
                # 添加工具结果（OpenAI 格式）
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": output
                })
        
        # 把工具结果加回消息历史
        messages.extend(results)


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        
        if query.strip().lower() in ("q", "exit", ""):
            break
        
        # 添加用户消息到历史
        history.append({"role": "user", "content": query})
        
        # 运行 Agent 循环
        agent_loop(history)
        
        # 打印最后一条回复
        response_content = history[-1].get("content", "")
        if response_content:
            print(response_content)
        print()
