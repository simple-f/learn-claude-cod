#!/usr/bin/env python3
"""
s12_worktree_task_isolation_openai.py - 工作树 + 任务隔离（OpenAI/阿里 CodingPlan 兼容版）

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 实现目录级隔离（worktree）+ 任务隔离（task）
- 兼容阿里 CodingPlan API

核心洞察：
"Isolate by directory, coordinate by task ID."
（按目录隔离，按任务 ID 协调）

架构图：
    .tasks/task_12.json
      {
        "id": 12,
        "subject": "Implement auth refactor",
        "status": "in_progress",
        "worktree": "auth-refactor"
      }

    .worktrees/index.json
      {
        "worktrees": [
          {
            "name": "auth-refactor",
            "path": ".../.worktrees/auth-refactor",
            "branch": "wt/auth-refactor",
            "task_id": 12,
            "status": "active"
          }
        ]
      }

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s12_worktree_task_isolation_openai.py
"""

import json
import os
import re
import subprocess
import time
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


def detect_repo_root(cwd: Path) -> Path | None:
    """检测 git 仓库根目录"""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return None
        root = Path(r.stdout.strip())
        return root if root.exists() else None
    except Exception:
        return None


REPO_ROOT = detect_repo_root(WORKDIR) or WORKDIR

SYSTEM = (
    f"You are a coding agent at {WORKDIR}. "
    "Use task + worktree tools for multi-task work. "
    "For parallel or risky changes: create tasks, allocate worktree lanes, "
    "run commands in those lanes, then choose keep/remove for closeout."
)


# ============================================================================
# EventBus - 事件总线
# ============================================================================

class EventBus:
    def __init__(self, event_log_path: Path):
        self.path = event_log_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("")

    def emit(self, event: str, task: dict = None, worktree: dict = None, error: str = None):
        payload = {
            "event": event,
            "ts": time.time(),
            "task": task or {},
            "worktree": worktree or {},
            "error": error,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(payload) + "\n")


EVENT_BUS = EventBus(WORKDIR / ".events" / "events.jsonl")


# ============================================================================
# Worktree Manager - 工作树管理器
# ============================================================================

class WorktreeManager:
    def __init__(self, worktrees_dir: Path):
        self.dir = worktrees_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "index.json"
        self.index = self._load_index()

    def _load_index(self) -> dict:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text())
        return {"worktrees": []}

    def _save_index(self):
        self.index_path.write_text(json.dumps(self.index, indent=2))

    def create(self, name: str, task_id: int) -> str:
        # 检查工作树是否已存在
        for wt in self.index["worktrees"]:
            if wt["name"] == name:
                return f"Error: Worktree '{name}' already exists"
        
        # 创建工作树
        worktree_path = self.dir / name
        branch_name = f"wt/{name}"
        
        try:
            # 添加工作树
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as e:
            return f"Error: Failed to create worktree: {e}"
        
        # 添加到索引
        wt_entry = {
            "name": name,
            "path": str(worktree_path),
            "branch": branch_name,
            "task_id": task_id,
            "status": "active",
            "created_at": time.time(),
        }
        self.index["worktrees"].append(wt_entry)
        self._save_index()
        
        EVENT_BUS.emit("worktree_created", worktree=wt_entry)
        return f"Created worktree '{name}' at {worktree_path}"

    def remove(self, name: str, force: bool = False) -> str:
        # 查找工作树
        wt = None
        for w in self.index["worktrees"]:
            if w["name"] == name:
                wt = w
                break
        
        if not wt:
            return f"Error: Worktree '{name}' not found"
        
        try:
            # 移除工作树
            cmd = ["git", "worktree", "remove"]
            if force:
                cmd.append("-f")
            cmd.append(wt["path"])
            
            subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        except Exception as e:
            return f"Error: Failed to remove worktree: {e}"
        
        # 从索引中删除
        self.index["worktrees"] = [w for w in self.index["worktrees"] if w["name"] != name]
        self._save_index()
        
        wt["status"] = "removed"
        EVENT_BUS.emit("worktree_removed", worktree=wt)
        return f"Removed worktree '{name}'"

    def list_all(self) -> str:
        if not self.index["worktrees"]:
            return "No worktrees."
        lines = []
        for wt in self.index["worktrees"]:
            lines.append(f"{wt['name']}: {wt['path']} (task #{wt['task_id']}, {wt['status']})")
        return "\n".join(lines)


WORKTREES = WorktreeManager(REPO_ROOT / ".worktrees")


# ============================================================================
# Task Manager - 任务管理器
# ============================================================================

class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._next_id = self._max_id() + 1

    def _max_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())

    def _save(self, task: dict):
        path = self.dir / f"task_{task['id']}.json"
        path.write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "", worktree: str = None) -> str:
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "blockedBy": [],
            "blocks": [],
            "owner": "",
            "worktree": worktree,
        }
        self._save(task)
        self._next_id += 1
        EVENT_BUS.emit("task_created", task=task)
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None, worktree: str = None) -> str:
        task = self._load(task_id)
        if status:
            task["status"] = status
        if worktree:
            task["worktree"] = worktree
        self._save(task)
        EVENT_BUS.emit("task_updated", task=task)
        return json.dumps(task, indent=2)

    def list_all(self) -> str:
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):
            tasks.append(json.loads(f.read_text()))
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            wt = f" (worktree: {t.get('worktree', 'none')})" if t.get("worktree") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{wt}")
        return "\n".join(lines)


TASKS = TaskManager(REPO_ROOT / ".tasks")


# ============================================================================
# Tool Implementations
# ============================================================================

def safe_path(p: str, worktree_name: str = None) -> Path:
    """安全路径检查（支持 worktree）"""
    if worktree_name:
        base = REPO_ROOT / ".worktrees" / worktree_name
    else:
        base = WORKDIR
    
    path = (base / p).resolve()
    try:
        path.relative_to(base)
        return path
    except ValueError:
        raise ValueError(f"Path escapes worktree: {p}")


def run_bash(command: str, worktree: str = None) -> str:
    """执行 bash 命令（支持 worktree 目录）"""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    
    cwd = REPO_ROOT / ".worktrees" / worktree if worktree else WORKDIR
    
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_task_create(subject: str, description: str = "", worktree: str = None) -> str:
    return TASKS.create(subject, description, worktree)


def run_task_list() -> str:
    return TASKS.list_all()


def run_task_update(task_id: int, status: str = None, worktree: str = None) -> str:
    return TASKS.update(task_id, status, worktree)


def run_worktree_create(name: str, task_id: int) -> str:
    return WORKTREES.create(name, task_id)


def run_worktree_remove(name: str, force: bool = False) -> str:
    return WORKTREES.remove(name, force)


def run_worktree_list() -> str:
    return WORKTREES.list_all()


TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"], kw.get("worktree")),
    "task_create": lambda **kw: run_task_create(kw["subject"], kw.get("description", ""), kw.get("worktree")),
    "task_list": lambda **kw: run_task_list(),
    "task_update": lambda **kw: run_task_update(kw["task_id"], kw.get("status"), kw.get("worktree")),
    "worktree_create": lambda **kw: run_worktree_create(kw["name"], kw["task_id"]),
    "worktree_remove": lambda **kw: run_worktree_remove(kw["name"], kw.get("force", False)),
    "worktree_list": lambda **kw: run_worktree_list(),
}


# ============================================================================
# Tool Definitions (OpenAI Format)
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in a worktree or main directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "worktree": {"type": "string", "description": "Worktree name (optional)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_create",
            "description": "Create a new task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "description": {"type": "string"},
                    "worktree": {"type": "string"}
                },
                "required": ["subject"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_list",
            "description": "List all tasks.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_update",
            "description": "Update task status or worktree.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                    "worktree": {"type": "string"}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "worktree_create",
            "description": "Create a new worktree for a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "task_id": {"type": "integer"}
                },
                "required": ["name", "task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "worktree_remove",
            "description": "Remove a worktree.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "force": {"type": "boolean"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "worktree_list",
            "description": "List all worktrees.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]


# ============================================================================
# Agent Loop
# ============================================================================

def agent_loop(messages: list):
    """【核心循环】Agent Loop with Worktree Isolation"""
    while True:
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
            try:
                args = json.loads(tool_call.function.arguments)
            except:
                results.append({"role": "tool", "tool_call_id": tool_call.id, "content": "Error: Invalid JSON"})
                continue
            
            handler = TOOL_HANDLERS.get(tool_call.function.name)
            if handler:
                try:
                    output = handler(**args)
                except Exception as e:
                    output = f"Error: {e}"
            else:
                output = f"Error: Unknown tool '{tool_call.function.name}'"
            
            print(f"> {tool_call.function.name}: {output[:200]}")
            results.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})
        
        messages.extend(results)


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms12 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        content = history[-1].get("content", "")
        if content:
            print(content)
        print()
