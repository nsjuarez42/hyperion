"""Workspace operations built on the IDE client: read or check a file, save and
validate a YAML file, describe what a file contains, and turn a validation
report into one chat message."""

import re

from agent.config import MAX_REPORTED_ERRORS
from agent.prompts import reply
from agent.templates.parsing import image_ref, split_image
from agent.tools.ide_client import (
    ReadFileError,
    create_workspace_file,
    read_file,
    validate_file,
    write_workspace_file,
)


async def read_existing(path: str) -> str | None:
    """The file's content, or None if it is not in the workspace."""
    try:
        return await read_file(path)
    except ReadFileError as exc:
        if "not in the workspace" in str(exc):
            return None
        raise


async def file_exists(path: str) -> bool:
    return await read_existing(path) is not None


async def save_yaml(path: str, content: str) -> dict:
    """Write the file (create or replace) and return the IDE's validation report.

    create_workspace_file fails if the path exists, so existing files are
    replaced with write_workspace_file instead.
    """
    if await file_exists(path):
        await write_workspace_file(path, content)
    else:
        await create_workspace_file(path, content)
    return await validate_file(path)


def _field(content: str, name: str) -> str | None:
    match = re.search(rf'^\s*{name}:\s*"?([^"\n]+?)"?\s*$', content, re.MULTILINE)
    return match.group(1) if match else None


def describe_yaml(content: str, spanish: bool = False) -> str:
    """A short summary of a file, shown before it is deleted or overwritten,
    e.g. "native application profile, image nginx:1.27, 26 lines"."""
    parts = []
    if re.search(r"^applicationProfile:", content, re.MULTILINE):
        parts.append(reply("native_profile", spanish))
        uri, tag = _field(content, "uri"), _field(content, "tag")
        if uri:
            parts.append(reply("image", spanish, image=image_ref(split_image(uri)[0], tag or "latest")))
    elif re.search(r"^kind:\s*Application", content, re.MULTILINE):
        parts.append(reply("device_manifest", spanish))
        workload = _field(content, "image") or _field(content, "apkUrl") or _field(content, "binaryUrl")
        if workload:
            parts.append(reply("image", spanish, image=workload))
    else:
        parts.append(reply("yaml_file", spanish))
    parts.append(reply("lines", spanish, count=len(content.splitlines())))
    return ", ".join(parts)


def format_report(report: dict, spanish: bool = False) -> str:
    if report.get("valid"):
        warnings = report.get("warnings") or []
        if not warnings:
            return reply("valid", spanish)
        return reply("valid_warnings", spanish, count=len(warnings))
    lines = [
        f"- {error.get('field') or '(root)'}: {error.get('message')}"
        for error in (report.get("errors") or [])[:MAX_REPORTED_ERRORS]
    ]
    return reply("invalid", spanish) + "\n" + "\n".join(lines)
