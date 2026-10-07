"""One IDE-action turn: plan it, then read, validate, delete or write a file.

Yields ("text", str), ("action", dict) or ("error", str) tuples; chat.py turns
them into SSE events.
"""

import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import tool_llm
from agent.language import is_spanish
from agent.prompts import YAML_REPAIR, YAML_REQUEST, YAML_SYSTEM, reply
from agent.templates import render_profile
from agent.templates.parsing import file_stem, service_name
from agent.templates.services import SKIP_NAMES
from agent.tools.confirm import pending
from agent.tools.files import describe_yaml, format_report, read_existing, save_yaml
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
    response = await tool_llm.ainvoke(
        [SystemMessage(content=YAML_SYSTEM), HumanMessage(content=human)]
    )
    return strip_fences(message_text(response))


def write_path(text: str, planned: str) -> str:
    """Keep a file name the user gave; otherwise name the file after the service.

    Left to the model, "create a deployment YAML for nginx" becomes
    deployment.yaml one run and service.yaml the next. nginx.yaml is stable
    and is what the user will ask about afterwards.
    """
    if planned:
        file_name = planned.rsplit("/", 1)[-1]
        stem = file_stem(planned)
        if file_name.lower() in text.lower():
            return planned
        if stem.lower() not in SKIP_NAMES and re.search(
            rf"\b{re.escape(stem)}\b", text, re.IGNORECASE
        ):
            return planned
    name = service_name(text)
    return f"{name}.yaml" if name else planned


async def stream_ide_action(user_id: str, text: str, history: list):
    """Yield ("text"|"action"|"error", payload) for one IDE-action turn."""
    spanish = is_spanish(text)
    try:
        op, raw_path = await plan(text, history)
        if op == "write":
            raw_path = write_path(text, raw_path)
        path = clean_path(raw_path) if raw_path else ""
        print(f"ide op={op} path={path or '(none)'} user={user_id}", flush=True)
        if op in ("read", "validate", "delete") and not path:
            yield ("text", reply("which_file", spanish))
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
            yield ("text", f"{path}: {format_report(report, spanish)}")
            return
        if op == "delete":
            current = await read_existing(path)
            if current is None:
                yield ("text", f"{path} is not in the workspace")
                return
            # Say what will be lost, so the yes/no is an informed one.
            pending[user_id] = {"op": "delete", "path": path, "spanish": spanish}
            details = f" ({describe_yaml(current, spanish)})"
            yield ("text", reply("confirm_delete", spanish, path=path, details=details))
            return

        content = render_profile(text, path)
        current = await read_existing(path)
        if current is not None:
            pending[user_id] = {
                "op": "overwrite",
                "path": path,
                "content": content,
                "spanish": spanish,
            }
            details = f" ({reply('currently', spanish)}{describe_yaml(current, spanish)})"
            yield ("text", reply("confirm_overwrite", spanish, path=path, details=details))
            return
        report = await save_yaml(path, content)
        if not report.get("valid"):
            content = await generate_yaml(text, path, content, format_report(report))
            report = await save_yaml(path, content)
        verdict = format_report(report, spanish)
        print(f"tool=write path={path} valid={report.get('valid')}", flush=True)
        yield ("text", reply("wrote", spanish, path=path, verdict=verdict))
        yield ("action", {"action": "edit_file", "path": path, "content": content})
    except (ReadFileError, ValidateFileError, WriteFileError) as exc:
        print(f"IDE action failed for {user_id}: {exc}")
        yield ("text", str(exc))
    except Exception as exc:
        print(f"IDE action error for {user_id}: {exc}")
        yield ("error", reply("llm_unavailable", spanish))
