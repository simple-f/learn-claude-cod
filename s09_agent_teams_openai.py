#!/usr/bin/env python3
"""
s09_agent_teams_openai.py - Agent 团队（OpenAI 兼容版）

核心洞察：
"Teammates that can talk to each other."
"""

import os
import subprocess
import threading
import time
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
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
TEAM_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = "You are a team member. Communicate via inbox messages."

VALID_MSG_TYPES = {"message", "broadcast"}


class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str, msg_type: str = "message") -> str:
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'"
        msg = {"type": msg_type, "from": sender, "content": content, "timestamp": time.time()}
        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

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

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        count = 0
        for name in teammates:
            if name != sender:
                self.send(sender, name, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"


BUS = MessageBus(INBOX_DIR)


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


def run_send_message(to: str, content: str) -> str:
    return BUS.send("user", to, content)


def run_read_inbox(name: str) -> str:
    messages = BUS.read_inbox(name)
    if not messages:
        return "Inbox empty."
    return "\n".join([f"[{m['type']}] From {m['from']}: {m['content']}" for m in messages])


def run_broadcast(content: str) -> str:
    teammates = [f.stem for f in INBOX_DIR.glob("*.jsonl")]
    return BUS.broadcast("user", content, teammates)


TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "send_message": lambda **kw: run_send_message(kw["to"], kw["content"]),
    "read_inbox": lambda **kw: run_read_inbox(kw["name"]),
    "broadcast": lambda **kw: run_broadcast(kw["content"]),
}

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "send_message", "description": "Send message to teammate.", "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}}, "required": ["to", "content"]}}},
    {"type": "function", "function": {"name": "read_inbox", "description": "Read your inbox.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "broadcast", "description": "Broadcast to all teammates.", "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}}},
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
            query = input("\033[36ms09 >> \033[0m")
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
