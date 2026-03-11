#!/usr/bin/env python3
"""
s07_task_system_openai.py - 任务系统（OpenAI/阿里 CodingPlan 兼容版）

核心洞察：
"State that survives compression -- because it's outside the conversation."
（状态存储在对话之外，压缩后不丢失）
"""

import os
import subprocess
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.environ.get("MODEL_ID", "qwen-coder-plus")
WORKDIR = Path.cwd()
TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)

SYSTEM = "You are a coding agent. Use task tools to plan and track work."


class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
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
        path = self.dir / f"task_{task_id}.json"
        path.write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "") -> str:
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "blockedBy": [],
            "blocks": [],
            "owner": "",
        }
        path = self.dir / f"task_{self._next_id}.json"
        path.write_text(json.dumps(task, indent=2))
        self._next_id += 1
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None, add_blocked_by: list = None) -> str:
        path = self.dir / f"task_{task_id}.json"
        task = json.loads(path.read_text())
        
        if status:
            task["status"] = status
            if status == "completed":
                self._clear_dependency(task_id)
        
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        
        path.write_text(json.dumps(task, indent=2))
        return json.dumps(task, indent=2)

    def _clear_dependency(self, completed_id: int):
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                f.write_text(json.dumps(task, indent=2))

    def list_all(self) -> str:
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):
            tasks.append(json.loads(f.read_text()))
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)


TASKS = TaskManager(TASKS_DIR)


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
        return (r.stdout + r.stderr).strip()[:50000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_task_create(subject: str, description: str = "") -> str:
    return TASKS.create(subject, description)


def run_task_list() -> str:
    return TASKS.list_all()


def run_task_update(task_id: int, status: str = None) -> str:
    return TASKS.update(task_id, status)


TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "task_create": lambda **kw: run_task_create(kw["subject"], kw.get("description", "")),
    "task_list": lambda **kw: run_task_list(),
    "task_update": lambda **kw: run_task_update(kw["task_id"], kw.get("status")),
}

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "task_create", "description": "Create a new task.", "parameters": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}}},
    {"type": "function", "function": {"name": "task_list", "description": "List all tasks.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "task_update", "description": "Update task status.", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["task_id"]}}},
]


def agent_loop(messages: list):
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
            output = handler(**args) if handler else f"Error: Unknown tool"
            print(f"> {tool_call.function.name}: {output[:200]}")
            results.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})
        
        messages.extend(results)


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms07 >> \033[0m")
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
