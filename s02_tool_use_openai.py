#!/usr/bin/env python3
"""
s02_tool_use_openai.py - 多工具系统（OpenAI/阿里 CodingPlan 兼容版）

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 支持 4 个工具：bash, read_file, write_file, edit_file
- 兼容阿里 CodingPlan API (DashScope)

核心洞察：
"The loop didn't change at all. I just added tools."
（循环完全没变，只是添加了工具）

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s02_tool_use_openai.py
"""

import os
import subprocess
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
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


# ============================================================================
# 安全检查
# ============================================================================

def safe_path(p: str) -> Path:
    """
    【安全检查】路径验证
    
    防止路径逃逸攻击（如 ../../../etc/passwd）
    """
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


# ============================================================================
# 工具实现
# ============================================================================

def run_bash(command: str) -> str:
    """
    【工具】执行 bash 命令
    
    【安全检查】
    - 黑名单过滤（rm -rf /, sudo, shutdown, reboot）
    - 超时限制（120 秒）
    - 输出截断（50000 字符）
    """
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
    """
    【工具】读取文件内容
    
    【参数】
    - path: 文件路径（必须在工作区内）
    - limit: 最大行数（可选，用于截断长文件）
    
    【安全】
    - 使用 safe_path 验证路径
    - 输出截断（50000 字符）
    """
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    """
    【工具】写入文件
    
    【特性】
    - 自动创建父目录（parents=True）
    - 覆盖已有文件
    
    【安全】
    - 使用 safe_path 验证路径
    """
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    【工具】精确文本替换
    
    【参数】
    - path: 文件路径
    - old_text: 要替换的原文（必须精确匹配）
    - new_text: 新文本
    
    【为什么用精确匹配？】
    - 避免误替换（如替换多个相同单词）
    - 强制 Agent 先读取文件确认内容
    
    【安全】
    - 使用 safe_path 验证路径
    """
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
# 工具注册 - Dispatch Map 模式
# ============================================================================

# 【工具分发器】用字典分发工具调用，易于扩展
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# 【工具定义】OpenAI 格式（与 Anthropic 格式不同）
TOOLS = [
    {
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read (must be within workspace)."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to return (optional)."
                    }
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
                    "path": {
                        "type": "string",
                        "description": "The file path to write to."
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write."
                    }
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
                    "path": {
                        "type": "string",
                        "description": "The file path to edit."
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The exact text to replace."
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The new text to replace with."
                    }
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
]


# ============================================================================
# Agent 循环
# ============================================================================

def agent_loop(messages: list):
    """
    【核心循环】Agent Loop with Tool Dispatch
    
    【OpenAI 格式 vs Anthropic 格式】
    
    Anthropic:
    - response.content -> [Block(...)]
    - block.type == "tool_use"
    - block.input -> dict
    
    OpenAI:
    - response.choices[0].message.tool_calls -> [ToolCall(...)]
    - tool_call.function.name -> str
    - tool_call.function.arguments -> JSON string
    
    【流程】
    1. 调用 LLM（传入 system + messages + tools）
    2. 如果有工具调用 → 执行工具
    3. 把工具结果加回消息历史
    4. 重复直到模型不调用工具
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
        if not assistant_message.tool_calls:
            # 没有工具调用，结束
            return
        
        # 执行工具调用
        results = []
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            # 解析 JSON 参数
            import json
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error: Invalid JSON arguments: {function_args}"
                })
                continue
            
            # 打印工具调用
            print(f"\033[33m$ {function_name}: {str(args)[:100]}\033[0m")
            
            # 调用对应的处理函数
            handler = TOOL_HANDLERS.get(function_name)
            if handler:
                try:
                    output = handler(**args)
                except Exception as e:
                    output = f"Error: {e}"
            else:
                output = f"Error: Unknown tool '{function_name}'"
            
            print(f"{output[:200]}")
            
            # 添加工具结果（OpenAI 格式）
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })
        
        # 把工具结果加回消息历史
        messages.extend(results)


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    """【交互式 CLI】"""
    history = []
    
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
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
