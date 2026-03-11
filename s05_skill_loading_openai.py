#!/usr/bin/env python3
"""
s05_skill_loading_openai.py - 技能加载（OpenAI/阿里 CodingPlan 兼容版）

修改说明：
- 使用 openai SDK 替代 anthropic SDK
- 双层注入架构：Layer 1（元数据）+ Layer 2（完整内容）
- 兼容阿里 CodingPlan API

核心洞察：
"Don't put everything in the system prompt. Load on demand."
（不要把所有指令都塞进 system prompt，按需加载）

架构图：
    Layer 1（便宜）：skill names in system prompt (~100 tokens/skill)
    Layer 2（按需）：full skill body in tool_result

使用方法：
1. pip install openai python-dotenv
2. 配置 .env 文件：DASHSCOPE_API_KEY=xxx
3. 创建 skills/<name>/SKILL.md 文件
4. python s05_skill_loading_openai.py
"""

import os
import re
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
SKILLS_DIR = WORKDIR / "skills"


# ============================================================================
# SkillLoader - 技能加载器
# ============================================================================

class SkillLoader:
    """
    【核心组件】SkillLoader - 技能加载与管理
    
    【双层架构】
    Layer 1: 技能元数据（简短描述，用于 system prompt）
    Layer 2: 完整技能内容（按需加载，通过 tool_result 返回）
    
    【目录结构】
    skills/
      pdf/
        SKILL.md  <-- frontmatter (name, description) + body
      code-review/
        SKILL.md
    """
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self._load_all()

    def _load_all(self):
        """扫描 skills 目录下所有 SKILL.md 文件"""
        if not self.skills_dir.exists():
            return
        
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            text = f.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", f.parent.name)
            self.skills[name] = {"meta": meta, "body": body, "path": str(f)}

    def _parse_frontmatter(self, text: str) -> tuple:
        """
        解析 YAML frontmatter（--- 分隔符之间）
        
        格式：
        ---
        name: pdf
        description: Process PDF files
        tags: file,media
        ---
        
        # Skill body here...
        """
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
        """
        Layer 1：返回所有技能的简短描述（用于 system prompt）
        
        输出格式：
          - pdf: Process PDF files [file,media]
          - code-review: Review code for issues [quality,git]
        """
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
        """
        Layer 2：返回指定技能的完整内容（用于 tool_result）
        
        输出格式：
        <skill name="pdf">
        Full PDF processing instructions...
        Step 1: ...
        Step 2: ...
        </skill>
        """
        skill = self.skills.get(name)
        if not skill:
            available = ", ".join(self.skills.keys())
            return f"Error: Unknown skill '{name}'. Available: {available}"
        
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"


# 创建全局 SkillLoader 实例
SKILL_LOADER = SkillLoader(SKILLS_DIR)


# ============================================================================
# 系统提示词
# ============================================================================

# Layer 1：技能元数据注入到 system prompt
skills_description = SKILL_LOADER.get_descriptions()
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
{skills_description}"""


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


def run_load_skill(name: str) -> str:
    """
    【工具】加载技能（Layer 2）
    
    【参数】
    name: 技能名称
    
    【返回】
    完整技能内容（XML 格式包装）
    
    【用途】
    - 按需加载技能，避免 system prompt 过大
    - 节省 token（只加载需要的技能）
    """
    return SKILL_LOADER.get_content(name)


# ============================================================================
# 工具注册
# ============================================================================

TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "load_skill": lambda **kw: run_load_skill(kw["name"]),
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
        # 【核心工具】load_skill - 按需加载技能
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "Load a skill's full instructions. Use before tackling unfamiliar topics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill name (e.g., 'pdf', 'code-review')."
                    }
                },
                "required": ["name"]
            }
        }
    },
]


# ============================================================================
# Agent 循环
# ============================================================================

def agent_loop(messages: list):
    """【核心循环】Agent Loop with Skill Loading"""
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
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": "Error: Invalid JSON"
                })
                continue
            
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
        
        messages.extend(results)


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    history = []
    
    while True:
        try:
            query = input("\033[36ms05 >> \033[0m")
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
