#!/usr/bin/env python3
"""
s03_todo_write_annotated.py - TodoWrite 任务管理（注解版）

【核心概念】
TodoWrite 让 Agent 能够追踪自己的进度——通过一个结构化的待办事项列表。

【设计思想】
1. 外部化状态：TodoManager 独立于对话历史，不占用 context tokens
2. 强制专注：只能有 1 个任务处于 in_progress 状态
3. 人类可见：渲染格式一眼看出进度

【架构图】
    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> | Tools   |
    |  prompt  |      |       |      | + todo  |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                                |
                    +-----------+-----------+
                    | TodoManager state     |
                    | [ ] task A            |
                    | [>] task B <- doing   |
                    | [x] task C            |
                    +-----------------------+

【关键洞察】
"The agent can track its own progress -- and I can see it."
（Agent 可以追踪自己的进度——而且人类也能看到）
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

# 如果有自定义 ANTHROPIC_BASE_URL，则移除默认的 AUTH TOKEN（避免冲突）
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]  # 模型 ID，如 claude-sonnet-4-5-20250929

# ============================================================================
# 系统提示词
# ============================================================================

# 【设计要点】
# 1. 明确角色：coding agent
# 2. 指令清晰：开始前标记 in_progress，完成后标记 completed
# 3. 优先工具：Prefer tools over prose（用工具而不是空谈）

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""


# ============================================================================
# TodoManager 类 - 任务管理器
# ============================================================================

class TodoManager:
    """
    【核心组件】TodoManager - 结构化状态管理
    
    【职责】
    1. 验证任务数据（最多 20 项、必须有 text、status 合法）
    2. 限制并发（只能有 1 个 in_progress）
    3. 渲染输出（视觉化进度）
    
    【为什么需要验证？】
    - 防止 LLM 滥用（最多 20 项）
    - 保证数据质量（text 必填）
    - 强制专注（只能 1 个进行中）
    """
    
    def __init__(self):
        """初始化任务列表"""
        self.items = []

    def update(self, items: list) -> str:
        """
        【核心方法】更新任务列表
        
        【参数】
        items: 任务列表，每项包含：
            - id: 任务 ID（可选，默认自增）
            - text: 任务描述（必填）
            - status: 状态（pending/in_progress/completed）
        
        【验证规则】
        1. 最多 20 个待办（防止滥用）
        2. text 必填（不能为空）
        3. status 必须是 pending/in_progress/completed
        4. 只能有 1 个 in_progress（强制专注）
        
        【返回】渲染后的任务列表文本
        
        【异常】
        - ValueError: 超过 20 项
        - ValueError: text 为空
        - ValueError: status 非法
        - ValueError: 多个 in_progress
        """
        # 规则 1：最多 20 个待办
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")
        
        validated = []
        in_progress_count = 0
        
        for i, item in enumerate(items):
            # 提取并验证字段
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
        """
        【渲染方法】将任务列表渲染为视觉化文本
        
        【输出格式】
        [ ] #1: 任务 A
        [>] #2: 任务 B <- 进行中
        [x] #3: 任务 C
        (1/3 completed)
        
        【标记说明】
        [ ] = pending（待办）
        [>] = in_progress（进行中）
        [x] = completed（已完成）
        """
        if not self.items:
            return "No todos."
        
        lines = []
        for item in self.items:
            # 根据状态选择标记
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]"
            }[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        
        # 统计完成度
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        
        return "\n".join(lines)


# 创建全局 TodoManager 实例
TODO = TodoManager()


# ============================================================================
# 工具实现
# ============================================================================

def safe_path(p: str) -> Path:
    """
    【安全检查】路径验证
    
    【目的】防止路径逃逸攻击（如 ../../../etc/passwd）
    
    【实现】
    1. 解析为绝对路径
    2. 检查是否在工作目录内
    3. 抛出异常如果逃逸
    
    【为什么重要？】
    - 保护敏感文件（/etc/passwd, ~/.ssh/id_rsa）
    - 限制 Agent 只能访问工作区
    """
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """
    【工具】执行 bash 命令
    
    【安全检查】
    1. 黑名单过滤（rm -rf /, sudo, shutdown, reboot）
    2. 超时限制（120 秒）
    3. 输出截断（50000 字符）
    
    【为什么需要黑名单？】
    - 防止危险命令（删除系统文件、重启服务器）
    - 保护系统安全
    """
    # 危险命令黑名单
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
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
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
        return f"Wrote {len(content)} bytes"
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
        
        # 检查原文是否存在
        if old_text not in content:
            return f"Error: Text not found in {path}"
        
        # 替换（只替换第一次出现）
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# 工具注册
# ============================================================================

# 【工具分发器】Dispatch Map 模式
# 用字典分发工具调用，易于扩展
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "todo":       lambda **kw: TODO.update(kw["items"]),  # 新增 todo 工具
}

# 【工具定义】告诉 LLM 可以调用什么工具
TOOLS = [
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
    {
        # 【新增工具】todo - 任务管理
        "name": "todo", 
        "description": "Update task list. Track progress on multi-step tasks.",
        "input_schema": {
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
    
    【为什么需要提醒？】
    - LLM 可能忘记更新任务状态
    - 强制保持任务列表最新
    - 人类可以看到进度
    
    【流程】
    1. 调用 LLM
    2. 执行工具调用
    3. 检查是否使用了 todo 工具
    4. 如果超过 3 轮没用，注入提醒
    5. 把结果加回消息历史
    """
    rounds_since_todo = 0  # 计数器：多少轮没用 todo 工具
    
    while True:
        # 调用 LLM
        response = client.messages.create(
            model=MODEL, 
            system=SYSTEM, 
            messages=messages,
            tools=TOOLS, 
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        
        # 如果模型不调用工具，结束
        if response.stop_reason != "tool_use":
            return
        
        results = []
        used_todo = False
        
        # 执行工具调用
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"
                
                print(f"> {block.name}: {str(output)[:200]}")
                results.append({
                    "type": "tool_result", 
                    "tool_use_id": block.id, 
                    "content": str(output)
                })
                
                # 检查是否使用了 todo 工具
                if block.name == "todo":
                    used_todo = True
        
        # 更新计数器
        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1
        
        # 注入提醒（如果超过 3 轮没用 todo）
        if rounds_since_todo >= 3:
            results.insert(0, {
                "type": "text", 
                "text": "<reminder>Update your todos.</reminder>"
            })
        
        # 把工具结果加回消息历史
        messages.append({"role": "user", "content": results})


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    """
    【交互式 CLI】
    
    【流程】
    1. 读取用户输入
    2. 添加到消息历史
    3. 运行 Agent 循环
    4. 打印最后一条回复
    """
    history = []
    
    while True:
        try:
            query = input("\033[36ms03 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        
        # 退出命令
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
