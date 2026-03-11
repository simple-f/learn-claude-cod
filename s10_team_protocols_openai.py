#!/usr/bin/env python3
"""
s10_team_protocols_openai.py - 团队协议（OpenAI 兼容版）

核心洞察：
"Same request_id correlation pattern, two domains."
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
TEAM_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = "You are a team lead. Manage shutdown and plan approval protocols."

VALID_MSG_TYPES = {"message", "shutdown_request", "shutdown_response", "plan_approval_response"}

shutdown_requests = {}
plan_requests = {}
_tracker_lock = threading.Lock()


class MessageBus:
    def __init__(self, inbox_dir: Path):
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str, msg_type: str = "message", extra: dict = None) -> str:
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'"
        msg = {"type": msg_type, "from": sender, "content": content, "timestamp": time.time()}
        if extra:
            msg.update(extra)
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


BUS = MessageBus(INBOX_DIR)


def run_request_shutdown(requester: str, target: str) -> str:
    request_id = str(uuid.uuid4())[:8]
    with _tracker_lock:
        shutdown_requests[request_id] = {"target": target, "status": "pending", "timestamp": time.time()}
    msg = {"type": "shutdown_request", "request_id": request_id, "requester": requester, "timestamp": time.time()}
    BUS.send(requester, target, json.dumps(msg), "shutdown_request")
    return f"Shutdown requested: {request_id} -> {target}"


def run_respond_to_shutdown(responder: str, request_id: str, approve: bool) -> str:
    with _tracker_lock:
        req = shutdown_requests.get(request_id)
        if not req:
            return f"Error: Unknown request {request_id}"
        req["status"] = "approved" if approve else "rejected"
    msg = {"type": "shutdown_response", "request_id": request_id, "approve": approve, "responder": responder}
    BUS.send(responder, req["target"], json.dumps(msg), "shutdown_response")
    return f"Shutdown {'approved' if approve else 'rejected'}: {request_id}"


def run_submit_plan(submitter: str, plan_text: str) -> str:
    request_id = str(uuid.uuid4())[:8]
    with _tracker_lock:
        plan_requests[request_id] = {"from": submitter, "status": "pending", "plan": plan_text}
    msg = {"type": "plan_approval", "request_id": request_id, "plan": plan_text, "submitter": submitter}
    BUS.send(submitter, "lead", json.dumps(msg))
    return f"Plan submitted: {request_id}"


def run_review_plan(reviewer: str, request_id: str, approve: bool, feedback: str = "") -> str:
    with _tracker_lock:
        req = plan_requests.get(request_id)
        if not req:
            return f"Error: Unknown request {request_id}"
        req["status"] = "approved" if approve else "rejected"
    msg = {"type": "plan_approval_response", "request_id": request_id, "approve": approve, "feedback": feedback}
    BUS.send(reviewer, req["from"], json.dumps(msg), "plan_approval_response")
    return f"Plan {'approved' if approve else 'rejected'}: {feedback}"


def run_read_inbox(name: str) -> str:
    messages = BUS.read_inbox(name)
    if not messages:
        return "Inbox empty."
    return "\n".join([f"[{m['type']}] {m['from']}: {m['content']}" for m in messages])


TOOL_HANDLERS = {
    "request_shutdown": lambda **kw: run_request_shutdown(kw["requester"], kw["target"]),
    "respond_to_shutdown": lambda **kw: run_respond_to_shutdown(kw["responder"], kw["request_id"], kw["approve"]),
    "submit_plan": lambda **kw: run_submit_plan(kw["submitter"], kw["plan_text"]),
    "review_plan": lambda **kw: run_review_plan(kw["reviewer"], kw["request_id"], kw["approve"], kw.get("feedback", "")),
    "read_inbox": lambda **kw: run_read_inbox(kw["name"]),
}

TOOLS = [
    {"type": "function", "function": {"name": "request_shutdown", "description": "Request teammate shutdown.", "parameters": {"type": "object", "properties": {"requester": {"type": "string"}, "target": {"type": "string"}}, "required": ["requester", "target"]}}},
    {"type": "function", "function": {"name": "respond_to_shutdown", "description": "Respond to shutdown request.", "parameters": {"type": "object", "properties": {"responder": {"type": "string"}, "request_id": {"type": "string"}, "approve": {"type": "boolean"}}, "required": ["responder", "request_id", "approve"]}}},
    {"type": "function", "function": {"name": "submit_plan", "description": "Submit plan for approval.", "parameters": {"type": "object", "properties": {"submitter": {"type": "string"}, "plan_text": {"type": "string"}}, "required": ["submitter", "plan_text"]}}},
    {"type": "function", "function": {"name": "review_plan", "description": "Review submitted plan.", "parameters": {"type": "object", "properties": {"reviewer": {"type": "string"}, "request_id": {"type": "string"}, "approve": {"type": "boolean"}, "feedback": {"type": "string"}}, "required": ["reviewer", "request_id", "approve"]}}},
    {"type": "function", "function": {"name": "read_inbox", "description": "Read inbox.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
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
            query = input("\033[36ms10 >> \033[0m")
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
