"""One IDE-action turn: plan it, then read, validate, delete or write a file.

Yields ("text", str), ("action", dict) or ("error", str) tuples; chat.py turns
them into SSE events.
"""

import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import tool_llm
from agent.prompts import LLM_UNAVAILABLE, YAML_REPAIR, YAML_REQUEST, YAML_SYSTEM
from agent.templates import render_profile
from agent.tools.confirm import pending
from agent.tools.files import file_exists, format_report, save_yaml
from agent.tools.ide_client import (
    ReadFileError,
    ValidateFileError,
    WriteFileError,
    read_file,
    validate_file,
)
from agent.tools.planner import clean_path, message_text, plan


def strip_fences(content: str) -> str:
    """The YAML document from a model reply, without markdown fences or chatter."""
    text = content.strip()
    match = re.fullmatch(r"```(?:yaml|yml)?\s*(.*?)```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    start = re.search(r"^(applicationProfile:|apiVersion:)", text, flags=re.MULTILINE)
    if start:
        return text[start.start() :].strip()
    return text


async def generate_yaml(
    request: str, path: str, previous: str = "", errors: str = ""
) -> str:
    """Ask the model for YAML. Only used to repair a template that failed validation."""
    if previous:
        human = YAML_REPAIR.format(path=path, request=request, errors=errors, previous=previous)
    else:
        human = YAML_REQUEST.format(path=path, request=request)
    reply = await tool_llm.ainvoke(
        [SystemMessage(content=YAML_SYSTEM), HumanMessage(content=human)]
    )
    return strip_fences(message_text(reply))


async def stream_ide_action(user_id: str, text: str, history: list):
    """Yield ("text"|"action"|"error", payload) for one IDE-action turn."""
    try:
        op, raw_path = await plan(text, history)
        path = clean_path(raw_path) if raw_path else ""
        print(f"ide op={op} path={path or '(none)'} user={user_id}", flush=True)
        if op in ("read", "validate", "delete") and not path:
            yield ("text", "Which file? Give me a path such as nginx.yaml.")
            return
        if op == "read":
            try:
                content = await read_file(path)
            except ReadFileError as exc:
                yield ("text", str(exc))
                return
            yield ("text", f"{path}:\n{content}")
            return
        if op == "validate":
            try:
                report = await validate_file(path)
            except ValidateFileError as exc:
                yield ("text", str(exc))
                return
            yield ("text", f"{path}: {format_report(report)}")
            return
        if op == "delete":
            if not await file_exists(path):
                yield ("text", f"{path} is not in the workspace")
                return
            pending[user_id] = {"op": "delete", "path": path}
            yield (
                "text",
                f"I'm about to delete {path}. Reply yes to confirm or no to cancel.",
            )
            return

        content = render_profile(text, path)
        if await file_exists(path):
            pending[user_id] = {"op": "overwrite", "path": path, "content": content}
            yield (
                "text",
                f"I'm about to overwrite {path}. Reply yes to confirm or no to cancel.",
            )
            return
        report = await save_yaml(path, content)
        if not report.get("valid"):
            content = await generate_yaml(text, path, content, format_report(report))
            report = await save_yaml(path, content)
        verdict = format_report(report)
        print(f"tool=write path={path} valid={report.get('valid')}", flush=True)
        if report.get("valid"):
            yield ("text", f"Wrote {path} and opened it in the editor. {verdict}")
        else:
            yield ("text", f"Wrote {path} and opened it in the editor. {verdict}")
        yield ("action", {"action": "edit_file", "path": path, "content": content})
    except (ReadFileError, ValidateFileError, WriteFileError) as exc:
        print(f"IDE action failed for {user_id}: {exc}")
        yield ("text", str(exc))
    except Exception as exc:
        print(f"IDE action error for {user_id}: {exc}")
        yield ("error", LLM_UNAVAILABLE)
