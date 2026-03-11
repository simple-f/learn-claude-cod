#!/usr/bin/env python3
"""
s01_agent_loop.py - The Agent Loop

一个 AI 编码助手的核心秘密就这一个模式：

    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results

    +----------+      +------+      +-------+
    |   User   | ---> | LLM  | ---> | Tool  |
    |  prompt  |      |      |      | execute|
    +----------+      +--+---+      +---+---+
                         ^            |
                         | tool_result|
                         +------------+
                       (loop continues)

这就是核心循环：把工具执行结果反馈给模型，直到模型决定停止。
生产级助手会在这之上叠加策略、钩子和生命周期控制。
"""

import os
import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

# 加载 .env 文件配置（支持环境变量覆盖）
load_dotenv(override=True)

# 如果有自定义 ANTHROPIC_BASE_URL，则移除默认的 AUTH TOKEN（避免冲突）
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 初始化 Anthropic 客户端
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]  # 模型 ID，如 claude-sonnet-4-5-20250929

# 系统提示词：定义 Agent 的角色和行为准则
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# 工具定义：告诉 LLM 可以调用什么工具
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]


def run_bash(command: str) -> str:
    """
    执行 bash 命令并返回输出
    
    安全检查：阻止危险命令（rm -rf、sudo、shutdown 等）
    超时限制：120 秒
    输出截断：最多 50000 字符
    """
    # 危险命令黑名单
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                          capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


# -- 核心模式：循环调用工具直到模型停止 --
def agent_loop(messages: list):
    """
    Agent 核心循环
    
    流程：
    1. 调用 LLM（传入消息和工具）
    2. 如果模型调用工具 → 执行工具 → 把结果加回消息
    3. 如果模型不调用工具 → 结束循环
    
    这就是"ReAct"模式的简化版：Reason + Act 循环
    """
    while True:
        # 调用 LLM
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        # 添加助手回复到历史
        messages.append({"role": "assistant", "content": response.content})
        
        # 如果模型没有调用工具，结束
        if response.stop_reason != "tool_use":
            return
        
        # 执行工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\033[33m$ {block.input['command']}\033[0m")  # 黄色显示命令
                output = run_bash(block.input["command"])
                print(output[:200])  # 打印前 200 字符
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })
        
        # 把工具结果加回消息历史（关键！让模型知道执行结果）
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    history = []
    while True:
        try:
            # 读取用户输入
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
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()
