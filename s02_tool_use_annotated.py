#!/usr/bin/env python3
"""
s02_tool_use.py - 工具调用系统

核心洞察：**循环完全没变，只是加了工具**。

s01 的 agent_loop 一行代码都不用改，只需要：
1. 在 TOOLS 数组里添加工具定义
2. 在 TOOL_HANDLERS 字典里添加处理函数

这就是可扩展的架构设计！

    +----------+      +-------+      +------------------+
    |   User   | ---> |  LLM  | ---> | Tool Dispatch    |
    |  prompt  |      |       |      | {                |
    +----------+      +---+---+      |   bash: run_bash |
                          ^          |   read: run_read |
                          |          |   write: run_wr  |
                          +----------+   edit: run_edit |
                          tool_result| }                |
                                     +------------------+
"""

import os
import subprocess
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

# 加载环境变量配置
load_dotenv(override=True)

# 如果有自定义 API 地址，移除默认 token（避免冲突）
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 工作目录（所有文件操作限制在此目录下）
WORKDIR = Path.cwd()

# 初始化客户端
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]  # 模型 ID

# 系统提示词
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


def safe_path(p: str) -> Path:
    """
    安全检查：确保文件路径不逃逸出工作目录
    
    这是重要的安全措施！防止 LLM 读取/写入系统文件。
    
    例子：
    - 安全："./test.txt" → /workspace/test.txt
    - 危险："../../../etc/passwd" → 抛出 ValueError
    """
    path = (WORKDIR / p).resolve()  # 解析为绝对路径
    if not path.is_relative_to(WORKDIR):  # 检查是否在工作目录内
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """执行 bash 命令（同 s01）"""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    """
    读取文件内容
    
    参数：
    - path: 文件路径（相对工作目录）
    - limit: 可选，限制返回行数
    
    安全检查：使用 safe_path 防止路径逃逸
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
    写入文件内容
    
    自动创建父目录（如果不存在）
    """
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    编辑文件：替换指定文本
    
    注意：只替换第一次出现的位置
    如果找不到 old_text，返回错误
    """
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))  # 只替换一次
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════
# 核心设计：工具分发器（Dispatch Map）
# ═══════════════════════════════════════════════════════════

# 工具处理函数字典：{工具名：处理函数}
# 这是可扩展的关键！添加新工具只需在这里注册
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# 工具定义（告诉 LLM 有哪些工具可用）
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]


def agent_loop(messages: list):
    """
    Agent 核心循环（和 s01 完全一样！）
    
    关键变化：使用 TOOL_HANDLERS 分发工具调用
    """
    while True:
        # 调用 LLM
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        
        # 如果模型没有调用工具，结束
        if response.stop_reason != "tool_use":
            return
        
        # 执行工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 🔑 关键：通过字典查找处理函数
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                print(f"> {block.name}: {output[:200]}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })
        
        # 把工具结果加回消息历史
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
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
