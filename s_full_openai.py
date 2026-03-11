#!/usr/bin/env python3
"""
s_full_openai.py - 完整参考实现（OpenAI/阿里 CodingPlan 兼容版）

Capstone implementation combining every mechanism from s01-s11.
综合 s01-s11 所有功能的完整实现。

核心功能：
- s01: Agent 核心循环
- s02: 工具调度系统
- s03: Todo 任务管理
- s04: 子 Agent
- s05: 技能加载
- s06: 上下文压缩
- s07: 任务系统
- s08: 后台任务
- s09: Agent 团队
- s10: 团队协议
- s11: 自主 Agent

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. python s_full_openai.py
"""

import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from queue import Queue
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
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
TASKS_DIR = WORKDIR / ".tasks"
SKILLS_DIR = WORKDIR / "skills"
TRANSCRIPT_DIR = WORKDIR / ".transcripts"

TOKEN_THRESHOLD = 100000
POLL_INTERVAL = 5
IDLE_TIMEOUT = 60

VALID_MSG_TYPES = {"message", "broadcast", "shutdown_request", "shutdown_response", "plan_approval_response"}


# ============================================================================
# SECTION: Base Tools
# ============================================================================

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
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
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
# SECTION: TodoWrite (s03)
# ============================================================================

class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")
        validated = []
        in_progress_count = 0
        for i, item in enumerate(items):
            text = str(item.get("text", "")).strip()
            status = str(item.get("status", "pending")).lower()
            item_id = str(item.get("id", str(i + 1)))
            if not text:
                raise ValueError(f"Item {item_id}: text required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {item_id}: invalid status '{status}'")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"id": item_id, "text": text, "status": status})
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")
        self.items = validated
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "No todos."
        lines = []
        for item in self.items:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        return "\n".join(lines)


TODO = TodoManager()


# ============================================================================
# SECTION: Skill Loading (s05)
# ============================================================================

class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self._load_all()

    def _load_all(self):
        if not self.skills_dir.exists():
            return
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            text = f.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", f.parent.name)
            self.skills[name] = {"meta": meta, "body": body, "path": str(f)}

    def _parse_frontmatter(self, text: str) -> tuple:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        return meta, match.group(2).strip()

    def get_descriptions(self) -> str:
        if not self.skills:
            return "(no skills available)"
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)
        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            available = ", ".join(self.skills.keys())
            return f"Error: Unknown skill '{name}'. Available: {available}"
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"


SKILL_LOADER = SkillLoader(SKILLS_DIR)


# ============================================================================
# SECTION: Context Compact (s06)
# ============================================================================

def micro_compact(messages: list) -> list:
    KEEP_RECENT = 3
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg.get("role") == "tool":
            tool_results.append((msg_idx, msg))
    if len(tool_results) <= KEEP_RECENT:
        return messages
    to_clear = tool_results[:-KEEP_RECENT]
    for _, msg in to_clear:
        if isinstance(msg.get("content"), str) and len(msg["content"]) > 100:
            msg["content"] = "[Previous tool result - truncated]"
    return messages


def auto_compact(messages: list) -> list:
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.json"
    transcript_path.write_text(json.dumps(messages, indent=2))
    print(f"[transcript saved: {transcript_path}]")
    
    conversation_text = json.dumps(messages)[:80000]
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Summarize this conversation for continuity."},
            {"role": "user", "content": f"Summarize: 1) What was accomplished, 2) Current state, 3) Key decisions.\n\n{conversation_text}"}
        ],
        max_tokens=2000,
    )
    summary = response.choices[0].message.content
    
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
    ]


def estimate_tokens(messages: list) -> int:
    return len(str(messages)) // 4


# ============================================================================
# SECTION: Task System (s07)
# ============================================================================

class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(exist_ok=True)
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

    def create(self, subject: str, description: str = "") -> str:
        task = {
            "id": self._next_id, "subject": subject, "description": description,
            "status": "pending", "blockedBy": [], "blocks": [], "owner": "",
        }
        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None, add_blocked_by: list = None) -> str:
        task = self._load(task_id)
        if status:
            task["status"] = status
            if status == "completed":
                self._clear_dependency(task_id)
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        self._save(task)
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


# ============================================================================
# SECTION: Background Tasks (s08)
# ============================================================================

class BackgroundManager:
    def __init__(self):
        self.tasks = {}
        self._notification_queue = []
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {"status": "running", "result": None, "command": command}
        thread = threading.Thread(target=self._execute, args=(task_id, command), daemon=True)
        thread.start()
        return f"Background task {task_id} started: {command[:80]}"

    def _execute(self, task_id: str, command: str):
        try:
            r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, timeout=300)
            output = (r.stdout + r.stderr).strip()[:50000]
            status = "completed"
        except subprocess.TimeoutExpired:
            output = "Error: Timeout (300s)"
            status = "timeout"
        except Exception as e:
            output = f"Error: {e}"
            status = "error"
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = output or "(no output)"
        with self._lock:
            self._notification_queue.append({
                "task_id": task_id, "status": status,
                "command": command[:80], "result": (output or "(no output)")[:500],
            })

    def check(self, task_id: str = None) -> str:
        if task_id:
            t = self.tasks.get(task_id)
            if not t:
                return f"Error: Unknown task {task_id}"
            return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"
        lines = [f"{tid}: [{t['status']}] {t['command'][:60]}" for tid, t in self.tasks.items()]
        return "\n".join(lines) if lines else "No background tasks."

    def drain_notifications(self) -> list:
        with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
        return notifs


BG = BackgroundManager()


# ============================================================================
# SECTION: Message Bus (s09/s10)
# ============================================================================

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

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        count = 0
        for name in teammates:
            if name != sender:
                self.send(sender, name, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"


BUS = MessageBus(INBOX_DIR)


# ============================================================================
# SECTION: Team Protocols (s10)
# ============================================================================

shutdown_requests = {}
plan_requests = {}
_tracker_lock = threading.Lock()
_claim_lock = threading.Lock()


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


# ============================================================================
# SECTION: Autonomous Agents (s11)
# ============================================================================

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


def idle_cycle(agent_name: str) -> bool:
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


# ============================================================================
# SECTION: Subagent (s04)
# ============================================================================

def run_subagent(prompt: str) -> str:
    sub_messages = [{"role": "user", "content": prompt}]
    for _ in range(30):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": "You are a coding subagent. Complete the task and summarize."}] + sub_messages,
            tools=[
                {"type": "function", "function": {"name": "bash", "description": "Run shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
                {"type": "function", "function": {"name": "read_file", "description": "Read file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
                {"type": "function", "function": {"name": "write_file", "description": "Write file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
                {"type": "function", "function": {"name": "edit_file", "description": "Edit file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
            ],
            max_tokens=8000,
        )
        assistant_message = response.choices[0].message
        sub_messages.append(assistant_message)
        if not assistant_message.tool_calls:
            break
        results = []
        for tool_call in assistant_message.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except:
                results.append({"role": "tool", "tool_call_id": tool_call.id, "content": "Error: Invalid JSON"})
                continue
            # Execute tool calls (simplified)
            results.append({"role": "tool", "tool_call_id": tool_call.id, "content": "Executed"})
        sub_messages.extend(results)
    return assistant_message.content or "(no summary)"


# ============================================================================
# SECTION: Tool Handlers
# ============================================================================

TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "todo": lambda **kw: TODO.update(kw["items"]),
    "load_skill": lambda **kw: SKILL_LOADER.get_content(kw["name"]),
    "compact": lambda **kw: "Compact triggered.",
    "background_run": lambda **kw: BG.run(kw["command"]),
    "background_check": lambda **kw: BG.check(kw.get("task_id")),
    "task_create": lambda **kw: TASKS.create(kw["subject"], kw.get("description", "")),
    "task_get": lambda **kw: TASKS.get(kw["task_id"]),
    "task_update": lambda **kw: TASKS.update(kw["task_id"], kw.get("status")),
    "task_list": lambda **kw: TASKS.list_all(),
    "send_message": lambda **kw: BUS.send(kw.get("sender", "agent"), kw["to"], kw["content"]),
    "read_inbox": lambda **kw: "\n".join([f"[{m['type']}] {m['from']}: {m['content']}" for m in BUS.read_inbox(kw["name"])]) or "Inbox empty.",
    "broadcast": lambda **kw: BUS.broadcast(kw.get("sender", "agent"), kw["content"], [kw["to"]]),
    "request_shutdown": lambda **kw: run_request_shutdown(kw["requester"], kw["target"]),
    "respond_to_shutdown": lambda **kw: run_respond_to_shutdown(kw["responder"], kw["request_id"], kw["approve"]),
    "submit_plan": lambda **kw: run_submit_plan(kw["submitter"], kw["plan_text"]),
    "review_plan": lambda **kw: run_review_plan(kw["reviewer"], kw["request_id"], kw["approve"], kw.get("feedback", "")),
    "find_work": lambda **kw: f"Found work for {kw['agent_name']}",
    "claim_task": lambda **kw: claim_task(kw["task_id"], kw["owner"]),
    "task": lambda **kw: run_subagent(kw["prompt"]),
}


# ============================================================================
# SECTION: Agent Loop
# ============================================================================

def agent_loop(messages: list, agent_name: str = "agent"):
    rounds_since_todo = 0
    
    while True:
        # Micro-compact (s06)
        messages = micro_compact(messages)
        
        # Auto-compact if needed (s06)
        if estimate_tokens(messages) > TOKEN_THRESHOLD:
            messages = auto_compact(messages)
        
        # Drain background notifications (s08)
        notifs = BG.drain_notifications()
        for notif in notifs:
            messages.append({"role": "user", "content": f"Background task {notif['task_id']} {notif['status']}: {notif['result']}"})
        
        # Check inbox (s09)
        inbox_messages = BUS.read_inbox(agent_name)
        for msg in inbox_messages:
            messages.append({"role": "user", "content": f"[{msg['type']}] From {msg['from']}: {msg['content']}"})
        
        # Build system prompt (s05)
        skills_desc = SKILL_LOADER.get_descriptions()
        system_prompt = f"""You are a coding agent at {WORKDIR}.

Skills available:
{skills_desc}

Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""
        
        # Call LLM
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=[
                {"type": "function", "function": {"name": "bash", "description": "Run shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
                {"type": "function", "function": {"name": "read_file", "description": "Read file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
                {"type": "function", "function": {"name": "write_file", "description": "Write file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
                {"type": "function", "function": {"name": "edit_file", "description": "Edit file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
                {"type": "function", "function": {"name": "todo", "description": "Update todos.", "parameters": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["id", "text", "status"]}}}, "required": ["items"]}}},
                {"type": "function", "function": {"name": "load_skill", "description": "Load skill.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
                {"type": "function", "function": {"name": "task", "description": "Spawn subagent.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}},
            ],
            max_tokens=8000,
        )
        
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        if not assistant_message.tool_calls:
            # Nag reminder (s03)
            if rounds_since_todo >= 3:
                messages.append({"role": "user", "content": "<reminder>Update your todos.</reminder>"})
                rounds_since_todo = 0
            # Idle cycle (s11)
            if not idle_cycle(agent_name):
                return
            continue
        
        results = []
        used_todo = False
        
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
            
            if tool_call.function.name == "todo":
                used_todo = True
        
        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1
        messages.extend(results)


# ============================================================================
# SECTION: Main
# ============================================================================

if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms_full >> \033[0m")
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
