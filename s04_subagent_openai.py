#!/usr/bin/env python3
"""
s04_subagent_openai.py - 子 Agent 系统（OpenAI/阿里 CodingPlan 兼容版）

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 实现上下文隔离：子 Agent 有全新的 messages=[]
- 兼容阿里 CodingPlan API

核心洞察：
"Process isolation gives context isolation for free."
（进程隔离免费赠送了上下文隔离）

架构图：
    Parent Agent                     Subagent
    +------------------+             +------------------+
    | messages=[...]   |             | messages=[]      |  <-- 全新上下文
    | tool: task       | ---------->| while tool_use:  |
    | prompt="..."     |            |   call tools     |
    |                  | <--------- | return summary   |
    +------------------+             +------------------+

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s04_subagent_openai.py
"""

import os
import subprocess
import json
from pathlib import Path
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
WORKDIR = Path.cwd()

# 系统提示词
SYSTEM = f"You are a coding agent at {WORKDIR}. Use the task tool to delegate exploration or subtasks."
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."


# ============================================================================
# 工具实现 - 父 Agent 和子 Agent 共享
# ============================================================================

def safe_path(p: str) -> Path:
    """【安全检查】路径验证"""
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """【工具】执行 bash 命令"""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    
    try:
        r = subprocess.run(
            command, 
            shell=True, 
            cwd=WORKDIR,
            capture_output=True, 
            text=True, 
            timeout=120
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    """【工具】读取文件内容"""
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    """【工具】写入文件"""
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """【工具】精确文本替换"""
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# 工具注册
# ============================================================================

TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# 【关键设计】子 Agent 的工具（没有 task 工具，不能递归派生）
CHILD_TOOLS = [
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
            "name": "write_file",
            "description": "Write content to file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace exact text in file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"}
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
]

# 【关键设计】父 Agent 的工具（包含 task 工具）
PARENT_TOOLS = CHILD_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "task",
            "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The task to delegate to the subagent."
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description of the task."
                    }
                },
                "required": ["prompt"]
            }
        }
    },
]


# ============================================================================
# 子 Agent 函数 - 核心组件
# ============================================================================

def run_subagent(prompt: str) -> str:
    """
    【核心函数】运行子 Agent
    
    【关键设计】
    1. 全新对话历史：sub_messages = [{"role": "user", "content": prompt}]
    2. 独立循环：最多 30 轮（安全限制）
    3. 只返回摘要：子 Agent 的完整上下文被丢弃
    """
    # 【关键】创建全新的对话历史
    sub_messages = [{"role": "user", "content": prompt}]
    
    # 运行子 Agent 循环（最多 30 轮）
    for _ in range(30):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SUBAGENT_SYSTEM}] + sub_messages,
            tools=CHILD_TOOLS,
            max_tokens=8000,
        )
        
        assistant_message = response.choices[0].message
        sub_messages.append(assistant_message)
        
        # 检查是否有工具调用
        if not assistant_message.tool_calls:
            break
        
        # 执行工具调用
        results = []
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Error: Invalid JSON"
                })
                continue
            
            handler = TOOL_HANDLERS.get(function_name)
            if handler:
                try:
                    output = handler(**args)
                except Exception as e:
                    output = f"Error: {e}"
            else:
                output = f"Error: Unknown tool '{function_name}'"
            
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })
        
        sub_messages.extend(results)
    
    # 【关键】只返回最终文本摘要（子 Agent 的完整上下文被丢弃）
    return assistant_message.content or "(no summary)"


# ============================================================================
# 父 Agent 循环
# ============================================================================

def agent_loop(messages: list):
    """
    【核心循环】父 Agent Loop
    
    【特殊处理】
    1. 使用 PARENT_TOOLS（包含 task 工具）
    2. task 工具调用 → 派生子 Agent
    3. 普通工具调用 → 直接执行
    """
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=PARENT_TOOLS,
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
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Error: Invalid JSON"
                })
                continue
            
            # 【特殊处理】task 工具 → 派生子 Agent
            if function_name == "task":
                desc = args.get("description", "subtask")
                print(f"> task ({desc}): {args['prompt'][:80]}")
                output = run_subagent(args["prompt"])
            else:
                # 普通工具 → 直接执行
                handler = TOOL_HANDLERS.get(function_name)
                if handler:
                    try:
                        output = handler(**args)
                    except Exception as e:
                        output = f"Error: {e}"
                else:
                    output = f"Error: Unknown tool '{function_name}'"
            
            print(f"  {str(output)[:200]}")
            
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })
        
        messages.extend(results)


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    history = []
    
    while True:
        try:
            query = input("\033[36ms04 >> \033[0m")
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
