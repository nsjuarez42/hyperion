"""Server-Sent Events as the IDE expects them.

A text payload becomes {"response": "..."} (appended to the chat); a dict is
sent as is, e.g. {"action": "edit_file", ...} (performed by the IDE).
"""

import json

DONE = "data: [DONE]\n\n"


def sse(payload: dict | str) -> str:
    if isinstance(payload, str):
        payload = {"response": payload}
    return f"data: {json.dumps(payload)}\n\n"
