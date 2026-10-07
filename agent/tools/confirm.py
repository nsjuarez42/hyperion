"""Human in the loop: deletes and overwrites wait for an explicit yes or no.

The pending action lives here per user_id. The yes/no is read in code, never
by the router or the model.
"""

import re

from agent.tools.files import format_report, save_yaml
from agent.tools.ide_client import ReadFileError, ValidateFileError, WriteFileError

pending: dict[str, dict] = {}


def interpret_confirmation(text: str) -> bool | None:
    """True for yes, False for no, None if the message is neither."""
    cleaned = re.sub(r"[.!?]+$", "", text.strip().lower())
    if re.fullmatch(r"(yes|y|yeah|yep|ok|okay|sure|confirm|do it|go ahead)", cleaned):
        return True
    if re.fullmatch(r"(no|n|nope|cancel|stop|don't|do not)( thanks)?", cleaned):
        return False
    if re.match(r"yes\b", cleaned):
        return True
    if re.match(r"(no|don't|do not|cancel)\b", cleaned):
        return False
    return None


def has_pending(user_id: str) -> bool:
    return user_id in pending


def cancel_pending(user_id: str) -> dict | None:
    """Drop a pending action when the user moves on instead of answering yes/no."""
    return pending.pop(user_id, None)


async def stream_pending(user_id: str, text: str):
    """A yes/no for a delete or overwrite is decided in code, not by the router."""
    action = pending.get(user_id)
    if action is None:
        return
    decision = interpret_confirmation(text)
    path = action["path"]
    if decision is None:
        yield (
            "text",
            f"I'm still waiting. Reply yes to {action['op']} {path}, or no to cancel.",
        )
        return
    pending.pop(user_id, None)
    if not decision:
        yield ("text", f"Cancelled. I left {path} unchanged.")
        return
    if action["op"] == "delete":
        yield ("text", f"Deleting {path}.")
        yield ("action", {"action": "delete_file", "path": path})
        return
    try:
        content = action["content"]
        report = await save_yaml(path, content)
    except (ReadFileError, ValidateFileError, WriteFileError) as exc:
        yield ("text", str(exc))
        return
    verdict = format_report(report)
    yield ("text", f"Overwrote {path} and opened it in the editor. {verdict}")
    yield ("action", {"action": "edit_file", "path": path, "content": content})
