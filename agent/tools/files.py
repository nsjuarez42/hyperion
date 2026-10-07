"""Workspace operations built on the IDE client: does a file exist, save and
validate a YAML file, and turn a validation report into one chat message."""

from agent.config import MAX_REPORTED_ERRORS
from agent.tools.ide_client import (
    ReadFileError,
    create_workspace_file,
    read_file,
    validate_file,
    write_workspace_file,
)


async def file_exists(path: str) -> bool:
    try:
        await read_file(path)
    except ReadFileError as exc:
        if "not in the workspace" in str(exc):
            return False
        raise
    return True


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


def format_report(report: dict) -> str:
    if report.get("valid"):
        warnings = report.get("warnings") or []
        if not warnings:
            return "Validation passed."
        return f"Validation passed with {len(warnings)} warning(s)."
    lines = [
        f"- {error.get('field') or '(root)'}: {error.get('message')}"
        for error in (report.get("errors") or [])[:MAX_REPORTED_ERRORS]
    ]
    return "Validation failed:\n" + "\n".join(lines)
