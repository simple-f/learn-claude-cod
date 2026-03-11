#!/usr/bin/env python3
"""
s04_subagent_annotated.py - 子 Agent 系统（注解版）

【核心概念】
Subagent - 通过进程隔离实现上下文隔离。子 Agent 有全新的对话历史，
父 Agent 的上下文保持干净。

【设计思想】
1. 上下文隔离：子 Agent 的 messages=[] 是全新的
2. 摘要返回：子 Agent 只返回总结，不返回完整上下文
3. 权限分离：子 Agent 没有 task 工具（不能递归派生）

【架构图】
    Parent Agent                     Subagent
    +------------------+             +------------------+
    | messages=[...]   |             | messages=[]      |  <-- 全新上下文
    |                  |  dispatch   |                  |
    | tool: task       | ---------->| while tool_use:  |
    |   prompt="..."   |            |   call tools     |
    |   description="" |            |   append results |
    |                  |  summary   |                  |
    |   result = "..." | <--------- | return last text |
    +------------------+             +------------------+
              |
    Parent context stays clean.
    Subagent context is discarded.

【关键洞察】
"Process isolation gives context isolation for free."
（进程隔离免费赠送了上下文隔离）

【与 s09 的区别】
- s04 Subagent: 用完即弃（spawn → execute → return → destroyed）
- s09 Teammate: 持久化（spawn → work → idle → work → ... → shutdown）
"""

import os
import subprocess
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

# ============================================================================
# 环境配置
# ============================================================================

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

# ============================================================================
# 系统提示词
# ============================================================================

# 父 Agent 的系统提示词 - 强调使用 task 工具委派任务
SYSTEM = f"You are a coding agent at {WORKDIR}. Use the task tool to delegate exploration or subtasks."

# 子 Agent 的系统提示词 - 强调完成任务并总结
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."


# ============================================================================
# 工具实现 - 父 Agent 和子 Agent 共享
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

# 【工具分发器】Dispatch Map 模式
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# ============================================================================
# 工具定义 - 子 Agent vs 父 Agent
# ============================================================================

# 【关键设计】子 Agent 的工具（没有 task 工具，不能递归派生）
# 防止无限嵌套（父→子→孙→...）
CHILD_TOOLS = [
    {
        "name": "bash", 
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object", 
            "properties": {"command": {"type": "string"}}, 
            "required": ["command"]
        }
    },
    {
        "name": "read_file", 
        "description": "Read file contents.",
        "input_schema": {
            "type": "object", 
            "properties": {
                "path": {"type": "string"}, 
                "limit": {"type": "integer"}
            }, 
            "required": ["path"]
        }
    },
    {
        "name": "write_file", 
        "description": "Write content to file.",
        "input_schema": {
            "type": "object", 
            "properties": {
                "path": {"type": "string"}, 
                "content": {"type": "string"}
            }, 
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file", 
        "description": "Replace exact text in file.",
        "input_schema": {
            "type": "object", 
            "properties": {
                "path": {"type": "string"}, 
                "old_text": {"type": "string"}, 
                "new_text": {"type": "string"}
            }, 
            "required": ["path", "old_text", "new_text"]
        }
    },
]

# 【关键设计】父 Agent 的工具（包含 task 工具）
# 只有父 Agent 可以派生子 Agent
PARENT_TOOLS = CHILD_TOOLS + [
    {
        # 【新增工具】task - 派生子 Agent
        "name": "task", 
        "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
        "input_schema": {
            "type": "object", 
            "properties": {
                "prompt": {"type": "string"}, 
                "description": {
                    "type": "string", 
                    "description": "Short description of the task"
                }
            }, 
            "required": ["prompt"]
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
    
    【参数】
    prompt: 子 Agent 的任务提示
    
    【返回】
    子 Agent 的最终文本摘要
    
    【流程】
    1. 创建全新对话历史（只有用户提示）
    2. 运行独立的 Agent 循环（最多 30 轮）
    3. 执行工具调用
    4. 返回最终文本（子 Agent 上下文被丢弃）
    
    【为什么限制 30 轮？】
    - 防止子 Agent 无限循环
    - 控制成本（token 消耗）
    - 强制子 Agent 尽快给出总结
    """
    # 【关键】创建全新的对话历史
    sub_messages = [{"role": "user", "content": prompt}]
    
    # 运行子 Agent 循环（最多 30 轮）
    for _ in range(30):
        # 调用 LLM
        response = client.messages.create(
            model=MODEL, 
            system=SUBAGENT_SYSTEM, 
            messages=sub_messages,
            tools=CHILD_TOOLS, 
            max_tokens=8000,
        )
        sub_messages.append({"role": "assistant", "content": response.content})
        
        # 如果模型不调用工具，结束
        if response.stop_reason != "tool_use":
            break
        
        # 执行工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                results.append({
                    "type": "tool_result", 
                    "tool_use_id": block.id, 
                    "content": str(output)[:50000]
                })
        sub_messages.append({"role": "user", "content": results})
    
    # 【关键】只返回最终文本摘要（子 Agent 的完整上下文被丢弃）
    return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"


# ============================================================================
# 父 Agent 循环
# ============================================================================

def agent_loop(messages: list):
    """
    【核心循环】父 Agent Loop
    
    【与 s01/s02 的区别】
    1. 使用 PARENT_TOOLS（包含 task 工具）
    2. 特殊处理 task 工具调用（派生子 Agent）
    3. 普通工具调用保持不变
    
    【流程】
    1. 调用 LLM
    2. 如果是 task 工具 → 派生子 Agent
    3. 如果是普通工具 → 直接执行
    4. 把结果加回消息历史
    """
    while True:
        # 调用 LLM（使用 PARENT_TOOLS）
        response = client.messages.create(
            model=MODEL, 
            system=SYSTEM, 
            messages=messages,
            tools=PARENT_TOOLS, 
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        
        # 如果模型不调用工具，结束
        if response.stop_reason != "tool_use":
            return
        
        results = []
        
        # 执行工具调用
        for block in response.content:
            if block.type == "tool_use":
                # 【特殊处理】task 工具 → 派生子 Agent
                if block.name == "task":
                    desc = block.input.get("description", "subtask")
                    print(f"> task ({desc}): {block.input['prompt'][:80]}")
                    output = run_subagent(block.input["prompt"])
                else:
                    # 普通工具 → 直接执行
                    handler = TOOL_HANDLERS.get(block.name)
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                
                print(f"  {str(output)[:200]}")
                results.append({
                    "type": "tool_result", 
                    "tool_use_id": block.id, 
                    "content": str(output)
                })
        
        # 把工具结果加回消息历史
        messages.append({"role": "user", "content": results})


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    """【交互式 CLI】"""
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
        
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()
