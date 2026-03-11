#!/usr/bin/env python3
"""
s06_context_compact_openai.py - 上下文压缩（OpenAI/阿里 CodingPlan 兼容版）

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 三层压缩管道：micro_compact → auto_compact → compact 工具
- 兼容阿里 CodingPlan API

核心洞察：
"The agent can forget strategically and keep working forever."
（Agent 可以战略性遗忘，永远工作下去）

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s06_context_compact_openai.py
"""

import os
import subprocess
import json
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件配置
load_dotenv(override=True)

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.environ.get("MODEL_ID", "qwen-coder-plus")
WORKDIR = Path.cwd()

SYSTEM = "You are a helpful coding assistant."

# 压缩阈值
THRESHOLD = 50000  # tokens
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
KEEP_RECENT = 3


def estimate_tokens(messages: list) -> int:
    """粗略估算 token 数量（~4 字符/token）"""
    return len(str(messages)) // 4


def micro_compact(messages: list) -> list:
    """
    Layer 1：微压缩（每回合执行）
    
    替换旧的 tool_result 为占位符
    """
    # 收集所有 tool_result
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg.get("role") == "tool":
            tool_results.append((msg_idx, msg))
    
    if len(tool_results) <= KEEP_RECENT:
        return messages
    
    # 清除旧的结果（保留最近 KEEP_RECENT 个）
    to_clear = tool_results[:-KEEP_RECENT]
    for idx, msg in to_clear:
        if isinstance(msg.get("content"), str) and len(msg["content"]) > 100:
            msg["content"] = "[Previous tool result - truncated]"
    
    return messages


def auto_compact(messages: list) -> list:
    """
    Layer 2：自动压缩（超过阈值时触发）
    
    1. 保存到 .transcripts/
    2. 让 LLM 总结对话
    3. 替换所有消息为总结
    """
    # 保存到磁盘
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.json"
    transcript_path.write_text(json.dumps(messages, indent=2))
    print(f"[transcript saved: {transcript_path}]")
    
    # 让 LLM 总结
    conversation_text = json.dumps(messages)[:80000]
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Summarize this conversation for continuity."},
            {"role": "user", "content": f"Summarize: 1) What was accomplished, 2) Current state, 3) Key decisions.\n\n{conversation_text}"}
        ],
        max_tokens=2000,
    )
    summary = response.choices[0].message.content
    
    # 替换为总结
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
    ]


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_compact() -> str:
    """【工具】手动触发压缩"""
    return "Compact triggered. Context will be compressed on next turn."


TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
    "compact": lambda **kw: run_compact(),
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compact",
            "description": "Manually trigger context compression.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]


def agent_loop(messages: list):
    """【核心循环】带压缩的 Agent Loop"""
    while True:
        # Layer 1：微压缩
        messages = micro_compact(messages)
        
        # 检查是否需要自动压缩
        if estimate_tokens(messages) > THRESHOLD:
            messages = auto_compact(messages)
        
        # 调用 LLM
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        if not assistant_message.tool_calls:
            return
        
        results = []
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                results.append({"role": "tool", "tool_call_id": tool_call.id, "content": "Error: Invalid JSON"})
                continue
            
            handler = TOOL_HANDLERS.get(function_name)
            if handler:
                try:
                    output = handler(**args)
                except Exception as e:
                    output = f"Error: {e}"
            else:
                output = f"Error: Unknown tool '{function_name}'"
            
            print(f"> {function_name}: {output[:200]}")
            results.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})
        
        messages.extend(results)


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms06 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1].get("content", "")
        if response_content:
            print(response_content)
        print()
