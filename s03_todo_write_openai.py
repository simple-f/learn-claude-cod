#!/usr/bin/env python3
"""
s03_todo_write_openai.py - 任务管理（OpenAI/阿里 CodingPlan 兼容版）

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 添加 todo 工具进行任务追踪
- 兼容阿里 CodingPlan API

核心洞察：
"The agent can track its own progress -- and I can see it."
（Agent 可以追踪自己的进度——而且人类也能看到）

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s03_todo_write_openai.py
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


# ============================================================================
# TodoManager - 任务管理器
# ============================================================================

class TodoManager:
    """
    【核心组件】TodoManager - 结构化状态管理
    
    【职责】
    1. 验证任务数据（最多 20 项、必须有 text、status 合法）
    2. 限制并发（只能有 1 个 in_progress）
    3. 渲染输出（视觉化进度）
    """
    
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        """
        【核心方法】更新任务列表
        
        【验证规则】
        1. 最多 20 个待办（防止滥用）
        2. text 必填（不能为空）
        3. status 必须是 pending/in_progress/completed
        4. 只能有 1 个 in_progress（强制专注）
        """
        # 规则 1：最多 20 个待办
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")
        
        validated = []
        in_progress_count = 0
        
        for i, item in enumerate(items):
            text = str(item.get("text", "")).strip()
            status = str(item.get("status", "pending")).lower()
            item_id = str(item.get("id", str(i + 1)))
            
            # 规则 2：text 必填
            if not text:
                raise ValueError(f"Item {item_id}: text required")
            
            # 规则 3：status 必须合法
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {item_id}: invalid status '{status}'")
            
            # 统计 in_progress 数量
            if status == "in_progress":
                in_progress_count += 1
            
            validated.append({"id": item_id, "text": text, "status": status})
        
        # 规则 4：只能有 1 个 in_progress
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")
        
        self.items = validated
        return self.render()

    def render(self) -> str:
        """【渲染方法】将任务列表渲染为视觉化文本"""
        if not self.items:
            return "No todos."
        
        lines = []
        for item in self.items:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]"
            }[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        
        return "\n".join(lines)


# 创建全局 TodoManager 实例
TODO = TodoManager()


# ============================================================================
# 系统提示词
# ============================================================================

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""


# ============================================================================
# 工具实现
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
    "todo":       lambda **kw: TODO.update(kw["items"]),
}

# 【工具定义】OpenAI 格式
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
    {
        # 【新增工具】todo - 任务管理
        "type": "function",
        "function": {
            "name": "todo",
            "description": "Update task list. Track progress on multi-step tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"]
                                }
                            },
                            "required": ["id", "text", "status"]
                        }
                    }
                },
                "required": ["items"]
            }
        }
    },
]


# ============================================================================
# Agent 循环 - 带提醒注入
# ============================================================================

def agent_loop(messages: list):
    """
    【核心循环】Agent Loop with Nag Reminder
    
    【特性】
    1. 追踪 rounds_since_todo（多少轮没用 todo 工具）
    2. 超过 3 轮自动注入提醒（<reminder>Update your todos.</reminder>）
    """
    rounds_since_todo = 0
    
    while True:
        # 调用 LLM
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        # 检查是否有工具调用
        if not assistant_message.tool_calls:
            return
        
        results = []
        used_todo = False
        
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            # 解析 JSON 参数
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error: Invalid JSON"
                })
                continue
            
            # 调用处理函数
            handler = TOOL_HANDLERS.get(function_name)
            if handler:
                try:
                    output = handler(**args)
                except Exception as e:
                    output = f"Error: {e}"
            else:
                output = f"Error: Unknown tool '{function_name}'"
            
            print(f"> {function_name}: {str(output)[:200]}")
            
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })
            
            if function_name == "todo":
                used_todo = True
        
        # 更新计数器
        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1
        
        # 注入提醒（如果超过 3 轮没用 todo）
        if rounds_since_todo >= 3:
            results.insert(0, {
                "role": "tool",
                "tool_call_id": "reminder",
                "content": "<reminder>Update your todos.</reminder>"
            })
        
        messages.extend(results)


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    history = []
    
    while True:
        try:
            query = input("\033[36ms03 >> \033[0m")
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
