"""Deciding the IDE operation (write, read, validate, delete) and the file path.

The model is asked for a tool call, but Llama 3.1 8B often writes the call as
JSON text instead, or skips it. So there are three layers: a real tool call,
JSON found in the text, and finally keyword rules on the user's sentence.
"""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from agent.config import PLANNER_HISTORY_MESSAGES
from agent.llm import tool_llm
from agent.prompts import PLAN_SYSTEM
from agent.tools.ide_client import WriteFileError

OPS = ("write", "read", "validate", "delete")


@tool
def plan_ide_action(op: str, path: str) -> str:
    """Choose the single IDE operation and the workspace path."""
    return "ok"


def message_text(message) -> str:
    """The text of a model reply, whether content is a string or a list of blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return ""


def clean_path(path: str) -> str:
    """A safe relative workspace path; rejects absolute paths and '..'."""
    cleaned = str(path or "").strip().strip("`").replace("\\", "/").lstrip("/")
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise WriteFileError("path must be a relative workspace path")
    return "/".join(parts)


def loose_plan(text: str) -> tuple[str, str] | None:
    """Recover a plan from a tool call the model wrote as JSON text."""
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    args = data.get("parameters") or data.get("args") or data.get("arguments") or data
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return None
    if not isinstance(args, dict):
        return None
    op = str(args.get("op") or data.get("name") or "").lower()
    path = str(args.get("path") or "")
    if op in ("write_workspace_file", "create_file", "edit_file"):
        op = "write"
    if op in ("read_workspace_file",):
        op = "read"
    if op in ("validate_workspace_file",):
        op = "validate"
    if op in ("delete_workspace_file", "delete_file"):
        op = "delete"
    if op not in OPS:
        return None
    return op, path


def fallback_plan(text: str) -> tuple[str, str]:
    """Keyword rules used when the model gives no usable plan."""
    named = re.search(r"([\w./-]+\.ya?ml)", text, flags=re.IGNORECASE)
    path = named.group(1) if named else ""
    lowered = text.lower()
    if any(word in lowered for word in ("delete", "remove")):
        return "delete", path
    if "valid" in lowered:
        return "validate", path
    if any(word in lowered for word in ("show", "read", "open", "display", "cat ")):
        return "read", path
    if not path:
        path = "nginx.yaml" if "nginx" in lowered else "app.yaml"
    return "write", path


async def plan(text: str, history: list) -> tuple[str, str]:
    try:
        reply = await tool_llm.bind_tools([plan_ide_action]).ainvoke(
            [
                SystemMessage(content=PLAN_SYSTEM),
                *history[-PLANNER_HISTORY_MESSAGES:],
                HumanMessage(content=text),
            ]
        )
    except Exception as exc:
        print(f"Planner error, using a keyword plan: {exc}")
        return fallback_plan(text)

    if reply.tool_calls:
        args = reply.tool_calls[0].get("args") or {}
        op = str(args.get("op") or "").strip().lower()
        path = str(args.get("path") or "")
        if op in OPS and path:
            return op, path
    loose = loose_plan(message_text(reply))
    if loose and loose[1]:
        return loose
    return fallback_plan(text)
