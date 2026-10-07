"""Reading what to deploy from the user's sentence: image, tag, port, device.

Plain regular expressions, no LLM: "Deploy nginx:1.27 to a phone on port 8080"
must always produce the same YAML.
"""

import re

from agent.templates.services import SERVICES, SKIP_NAMES


def file_stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def basename_of(image: str) -> str:
    return image.rsplit("/", 1)[-1]


def image_ref(image: str, tag: str) -> str:
    """nginx:1.27 for Docker Hub official images, the full URI otherwise."""
    if image.startswith("docker.io/library/"):
        return f"{basename_of(image)}:{tag}"
    return f"{image}:{tag}"


# "port 8080", "puerto 8080", "on 8080" (4-5 digits only, so "on 10 nodes" is
# not a port) and " :8080" (after a space, so the tag in "postgres:16" is not).
PORT = re.compile(
    r"\b(?:port|puerto)\s*(\d{2,5})\b|\bon\s+(\d{4,5})\b|(?:^|\s):(\d{2,5})\b",
    re.IGNORECASE,
)


def extract_port(text: str, default: int) -> int:
    match = PORT.search(text)
    if not match:
        return default
    port = int(next(group for group in match.groups() if group))
    return port if 1 <= port <= 65535 else default


def split_image(ref: str) -> tuple[str, str | None]:
    """'nginx:1.27' -> ('docker.io/library/nginx', '1.27')."""
    ref = ref.strip().strip("`").rstrip(".,)")
    tag = None
    if ":" in ref.split("/")[-1]:
        ref, tag = ref.rsplit(":", 1)
    if ref and "/" not in ref:
        ref = f"docker.io/library/{ref}"
    return ref, tag


def extract_image_ref(text: str) -> str | None:
    """The first thing in the sentence that looks like a container image."""
    patterns = (
        r"\b((?:[a-z0-9.-]+\.)+[a-z]{2,}/[a-z0-9._/-]+(?::[a-z0-9._-]+)?)\b",
        r"\b([a-z0-9][\w.-]*(?:/[a-z0-9][\w.-]*)*:[a-zA-Z0-9][\w.-]*)\b",
        r"using (?:the )?([a-z0-9][\w./:-]*?)(?:\s+docker)?\s+image",
        r"\bimage\s+([a-z0-9][\w./:-]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            ref = match.group(1).strip().rstrip(".,)")
            if (
                ref.lower() in SKIP_NAMES
                or ref.lower().split("/")[-1].split(":")[0] in SKIP_NAMES
            ):
                continue
            return ref
    return None


def service_name(request: str) -> str | None:
    """The service the sentence is about (nginx, redis, ...), or None."""
    ref = extract_image_ref(request)
    if ref:
        return basename_of(split_image(ref)[0]).lower()
    for name in SERVICES:
        if re.search(rf"\b{name}\b", request, re.IGNORECASE):
            return name
    return None


def resolve_service(request: str, path: str) -> tuple[str, str, str, int, str]:
    """Return image, tag, entrypoint, port, and YAML args for a container."""
    stem = file_stem(path)
    ref = extract_image_ref(request)
    image, tag = split_image(ref) if ref else (None, None)
    key = basename_of(image).lower() if image else None
    if key not in SERVICES:
        for name in SERVICES:
            if (
                re.search(rf"\b{name}\b", request, re.IGNORECASE)
                or name in stem.lower()
            ):
                key = name
                break
    if key not in SERVICES:
        named = re.search(
            r"\bfor (?:a |an |the )?([a-z0-9][\w.-]+)", request, re.IGNORECASE
        )
        if named and named.group(1).lower() not in SKIP_NAMES:
            key = named.group(1).lower()
    if key in SERVICES:
        catalog_image, catalog_tag, entry, port, args = SERVICES[key]
        image = image or catalog_image
        tag = tag or catalog_tag
    else:
        if image is None:
            guess = stem if stem.lower() not in SKIP_NAMES else "nginx"
            image, guessed_tag = split_image(guess)
            tag = tag or guessed_tag
        entry = basename_of(image)
        port = 80
        args = '["-g", "daemon off;"]' if entry == "nginx" else "[]"
        tag = tag or "latest"
    return image, tag or "latest", entry, extract_port(request, port), args


def device_kind(text: str) -> str | None:
    """esp32, android or docker (a container on a phone/glasses), or None for native."""
    lowered = text.lower()
    if "esp32" in lowered:
        return "esp32"
    if "apk" in lowered or "android" in lowered:
        return "android"
    if any(
        word in lowered
        for word in (
            "phone",
            "glasses",
            "devicenode",
            "device node",
            "device app",
            "on a device",
        )
    ):
        return "docker"
    return None
