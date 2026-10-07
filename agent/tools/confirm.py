"""Human in the loop: deletes and overwrites wait for an explicit yes or no.

The pending action lives here per user_id, with the language it was asked in.
The yes/no is read in code, never by the router or the model.
"""

import re

from agent.prompts import reply
from agent.tools.files import format_report, save_yaml
from agent.tools.ide_client import ReadFileError, ValidateFileError, WriteFileError

pending: dict[str, dict] = {}

YES = r"yes|y|yeah|yep|ok|okay|sure|confirm|do it|go ahead|sí|si|vale|claro|adelante|confirmo|hazlo"
NO = r"no|n|nope|cancel|stop|don't|do not|cancela|cancelar|para"


def interpret_confirmation(text: str) -> bool | None:
    """True for yes, False for no, None if the message is neither."""
    cleaned = re.sub(r"[.!?¡¿]+", "", text.strip().lower()).strip()
    if re.fullmatch(rf"({YES})( please| por favor)?", cleaned):
        return True
    if re.fullmatch(rf"({NO})( thanks| gracias)?", cleaned):
        return False
    # "yes, delete it" / "sí, bórralo"; plain "si" is left out here because
    # in Spanish it also means "if".
    if re.match(r"(yes|sí)\b", cleaned):
        return True
    if re.match(r"(no|don't|do not|cancel|cancela)\b", cleaned):
        return False
    return None


def has_pending(user_id: str) -> bool:
    return user_id in pending


def cancel_pending(user_id: str) -> dict | None:
    """Drop a pending action when the user moves on instead of answering yes/no."""
    return pending.pop(user_id, None)


def operation_name(action: dict) -> str:
    return reply(f"op_{action['op']}", action.get("spanish", False))


async def stream_pending(user_id: str, text: str):
    """A yes/no for a delete or overwrite is decided in code, not by the router."""
    action = pending.get(user_id)
    if action is None:
        return
    spanish = action.get("spanish", False)
    decision = interpret_confirmation(text)
    path = action["path"]
    if decision is None:
        yield ("text", reply("still_waiting", spanish, op=operation_name(action), path=path))
        return
    pending.pop(user_id, None)
    if not decision:
        yield ("text", reply("cancelled", spanish, path=path))
        return
    if action["op"] == "delete":
        yield ("text", reply("deleting", spanish, path=path))
        yield ("action", {"action": "delete_file", "path": path})
        return
    try:
        content = action["content"]
        report = await save_yaml(path, content)
    except (ReadFileError, ValidateFileError, WriteFileError) as exc:
        yield ("text", str(exc))
        return
    verdict = format_report(report, spanish)
    yield ("text", reply("overwrote", spanish, path=path, verdict=verdict))
    yield ("action", {"action": "edit_file", "path": path, "content": content})
