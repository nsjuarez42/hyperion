import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from helpers import (
    ReadFileError,
    ValidateFileError,
    WriteFileError,
    create_workspace_file,
    read_file,
    validate_file,
    write_workspace_file as save_existing_file,
)

load_dotenv()

API_KEY = os.environ.get("API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://legion1.di.uoa.gr/v1")
MODEL = os.environ.get("MODEL", "llama3.1")

tool_llm = ChatOpenAI(
    model=MODEL,
    base_url=BASE_URL,
    api_key=API_KEY or "missing",
    temperature=0,
    max_completion_tokens=2048,
)

OPS = ("write", "read", "validate", "delete")
pending: dict[str, dict] = {}

PLAN_SYSTEM = """You plan one IDE file action. Call plan_ide_action and nothing else.
op is write (create or replace a file), read (show a file), validate (check a file), or delete.
path is a relative workspace path ending in .yaml. If the user does not give a name, choose a short one from the request, such as nginx.yaml.
"""

YAML_SYSTEM = """You write HyperAI IDE YAML. Reply with the YAML document only. No markdown fences and no explanation.
A service, deployment, or container is a native application profile. Adapt this example: change the name, image, tag, entry point, and port to match the request. Keep versions and schemaVersion in quotes.

applicationProfile:
  metadata:
    type: "native"
    schemaVersion: "1.1.0"
    name: "nginx"
    version: "1.27.0"
    description: "Nginx web server."
    owner: "hyperion"
    lifecyclePhase: "development"
  specs:
    runtime:
      executionType: "container"
      entryPoint: "nginx"
      args: ["-g", "daemon off;"]
      baseOS:
        name: "debian"
        version: "12"
      containerImage:
        uri: "docker.io/library/nginx"
        tag: "1.27"
    resources:
      cpu: "100m"
      memory: "128Mi"
      storage: "1Gi"
    network:
      ports:
        - port: 80
          protocol: "TCP"
    constraints:
      supportedArchitectures: ["amd64"]

A phone, glasses, ESP32, or other device is a device manifest with apiVersion hyper.ai/v1, kind Application, spec.app.type device, and exactly one workload block (dockerImage, androidApk, or esp32Binary), plus network, qos, and constraints.
"""


@tool
def plan_ide_action(op: str, path: str) -> str:
    """Choose the single IDE operation and the workspace path."""
    return "ok"


def message_text(message) -> str:
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
    cleaned = str(path or "").strip().strip("`").replace("\\", "/").lstrip("/")
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise WriteFileError("path must be a relative workspace path")
    return "/".join(parts)


def strip_fences(content: str) -> str:
    text = content.strip()
    match = re.fullmatch(r"```(?:yaml|yml)?\s*(.*?)```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    start = re.search(r"^(applicationProfile:|apiVersion:)", text, flags=re.MULTILINE)
    if start:
        return text[start.start() :].strip()
    return text


def loose_plan(text: str) -> tuple[str, str] | None:
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


def format_report(report: dict) -> str:
    if report.get("valid"):
        warnings = report.get("warnings") or []
        if not warnings:
            return "Validation passed."
        return f"Validation passed with {len(warnings)} warning(s)."
    lines = [
        f"- {error.get('field') or '(root)'}: {error.get('message')}"
        for error in (report.get("errors") or [])[:8]
    ]
    return "Validation failed:\n" + "\n".join(lines)


async def file_exists(path: str) -> bool:
    try:
        await read_file(path)
    except ReadFileError as exc:
        if "not in the workspace" in str(exc):
            return False
        raise
    return True


async def plan(text: str, history: list) -> tuple[str, str]:
    try:
        reply = await tool_llm.bind_tools([plan_ide_action]).ainvoke(
            [
                SystemMessage(content=PLAN_SYSTEM),
                *history[-4:],
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


NATIVE_TEMPLATE = """applicationProfile:
  metadata:
    type: "native"
    schemaVersion: "1.1.0"
    name: "{name}"
    version: "1.0.0"
    description: "{description}"
    owner: "hyperion"
    lifecyclePhase: "development"
  specs:
    runtime:
      executionType: "container"
      entryPoint: "{entry}"
      args: {args}
      baseOS:
        name: "debian"
        version: "12"
      containerImage:
        uri: "{image}"
        tag: "{tag}"
    resources:
      cpu: "100m"
      memory: "128Mi"
      storage: "1Gi"
    network:
      ports:
        - port: {port}
          protocol: "TCP"
    constraints:
      supportedArchitectures: ["amd64"]
"""

SERVICES = {
    "nginx": ("docker.io/library/nginx", "1.27", "nginx", 80, '["-g", "daemon off;"]'),
    "redis": ("docker.io/library/redis", "7", "redis-server", 6379, "[]"),
    "postgres": ("docker.io/library/postgres", "16", "postgres", 5432, "[]"),
}


def fill(template: str, **values: object) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def render_native(request: str, path: str) -> str:
    """A known-valid native profile. The 8B model invents schemas, so code fills this one."""
    lowered = request.lower()
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    image, tag, entry, port, args = SERVICES["nginx"]
    for key, spec in SERVICES.items():
        if key in lowered or key in name.lower():
            image, tag, entry, port, args = spec
            break
    description = f"{name} service"
    return fill(
        NATIVE_TEMPLATE,
        name=name,
        description=description,
        entry=entry,
        args=args,
        image=image,
        tag=tag,
        port=port,
    )


async def generate_yaml(request: str, path: str, previous: str = "", errors: str = "") -> str:
    if previous:
        human = (
            f"File: {path}\nRequest: {request}\n\n"
            f"This YAML failed validation:\n{errors}\n\n{previous}\n\n"
            "Reply with the corrected YAML only."
        )
    else:
        human = f"File: {path}\nRequest: {request}\nReply with the YAML only."
    reply = await tool_llm.ainvoke(
        [SystemMessage(content=YAML_SYSTEM), HumanMessage(content=human)]
    )
    return strip_fences(message_text(reply))


async def save_yaml(path: str, content: str) -> dict:
    if await file_exists(path):
        await save_existing_file(path, content)
    else:
        await create_workspace_file(path, content)
    return await validate_file(path)


def interpret_confirmation(text: str) -> bool | None:
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

        if any(word in text.lower() for word in ("android", "apk", "esp32", "phone", "glasses")):
            content = await generate_yaml(text, path)
        else:
            content = render_native(text, path)
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
        yield ("error", "Sorry, I could not reach the language model.")
