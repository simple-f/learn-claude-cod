#!/usr/bin/env python3
"""
s11_autonomous_agents_openai.py - 自主 Agent（OpenAI 兼容版）

核心洞察：
"The agent finds work itself."
"""

import os
import subprocess
import threading
import time
import json
import uuid
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
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
TASKS_DIR = WORKDIR / ".tasks"
TEAM_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(exist_ok=True)

SYSTEM = "You are an autonomous agent. Find work yourself."

POLL_INTERVAL = 5
IDLE_TIMEOUT = 60

VALID_MSG_TYPES = {"message", "broadcast"}

_claim_lock = threading.Lock()


class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str, msg_type: str = "message") -> str:
        msg = {"type": msg_type, "from": sender, "content": content, "timestamp": time.time()}
        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent to {to}"

    def read_inbox(self, name: str) -> list:
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        messages = []
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                messages.append(json.loads(line))
        inbox_path.write_text("")
        return messages


BUS = MessageBus(INBOX_DIR)


def scan_unclaimed_tasks() -> list:
    unclaimed = []
    for f in sorted(TASKS_DIR.glob("task_*.json")):
        task = json.loads(f.read_text())
        if task.get("status") == "pending" and not task.get("owner") and not task.get("blockedBy"):
            unclaimed.append(task)
    return unclaimed


def claim_task(task_id: int, owner: str) -> str:
    with _claim_lock:
        path = TASKS_DIR / f"task_{task_id}.json"
        if not path.exists():
            return f"Error: Task {task_id} not found"
        task = json.loads(path.read_text())
        task["owner"] = owner
        task["status"] = "in_progress"
        path.write_text(json.dumps(task, indent=2))
    return f"Claimed task #{task_id} for {owner}"


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


def run_find_work(agent_name: str) -> str:
    # 检查收件箱
    messages = BUS.read_inbox(agent_name)
    if messages:
        return f"Found {len(messages)} messages in inbox."
    
    # 扫描任务
    unclaimed = scan_unclaimed_tasks()
    if unclaimed:
        task = unclaimed[0]
        claim_task(task["id"], agent_name)
        return f"Claimed task #{task['id']}: {task['subject']}"
    
    return "No work found."


TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "find_work": lambda **kw: run_find_work(kw["agent_name"]),
}

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "find_work", "description": "Find work (inbox messages or unclaimed tasks).", "parameters": {"type": "object", "properties": {"agent_name": {"type": "string"}}, "required": ["agent_name"]}}},
]


def idle_cycle(agent_name: str) -> bool:
    """空闲循环：轮询工作"""
    start_time = time.time()
    while time.time() - start_time < IDLE_TIMEOUT:
        messages = BUS.read_inbox(agent_name)
        if messages:
            return True
        
        unclaimed = scan_unclaimed_tasks()
        if unclaimed:
            task = unclaimed[0]
            claim_task(task["id"], agent_name)
            print(f"[{agent_name}] claimed task #{task['id']}")
            return True
        
        time.sleep(POLL_INTERVAL)
    
    print(f"[{agent_name}] idle timeout")
    return False


def agent_loop(messages: list, agent_name: str = "agent"):
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
            # 进入空闲循环
            if not idle_cycle(agent_name):
                return
            continue
        
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
            query = input("\033[36ms11 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history, "agent")
        content = history[-1].get("content", "")
        if content:
            print(content)
        print()
