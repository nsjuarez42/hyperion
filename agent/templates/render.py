"""Filling a YAML template from a request. Code fills the schema; the model does not invent it."""

import re

from agent.templates.parsing import (
    device_kind,
    extract_port,
    file_stem,
    image_ref,
    resolve_service,
)
from agent.templates.profiles import (
    DEVICE_ANDROID,
    DEVICE_DOCKER,
    DEVICE_ESP32,
    NATIVE_TEMPLATE,
)


def fill(template: str, **values: object) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def render_native(request: str, path: str) -> str:
    """A known-valid native profile."""
    name = file_stem(path)
    image, tag, entry, port, args = resolve_service(request, path)
    return fill(
        NATIVE_TEMPLATE,
        name=name,
        description=f"{name} service",
        entry=entry,
        args=args,
        image=image,
        tag=tag,
        port=port,
    )


def render_device(request: str, path: str, kind: str) -> str:
    name = file_stem(path)
    description = f"{name} device application"
    port = extract_port(request, 80)
    if kind == "android":
        apk = re.search(r"https?://\S+?\.apk", request, re.IGNORECASE)
        package = re.search(r"\bcom(?:\.[a-zA-Z0-9_]+)+\b", request)
        return fill(
            DEVICE_ANDROID,
            name=name,
            description=description,
            apk_url=(
                apk.group(0).rstrip(".,)") if apk else "https://example.com/app.apk"
            ),
            package=(package.group(0) if package else "com.example.app"),
            port=port,
        )
    if kind == "esp32":
        binary = re.search(r"https?://\S+?\.bin", request, re.IGNORECASE)
        chip = "esp32"
        for candidate in (
            "esp32h2",
            "esp32c6",
            "esp32c3",
            "esp32s3",
            "esp32s2",
            "esp32",
        ):
            if candidate in request.lower():
                chip = candidate
                break
        method = "serial" if "serial" in request.lower() else "ota"
        return fill(
            DEVICE_ESP32,
            name=name,
            description=description,
            binary_url=(
                binary.group(0).rstrip(".,)")
                if binary
                else "https://example.com/firmware.bin"
            ),
            chip=chip,
            flash_method=method,
            port=port,
        )
    image, tag, _entry, port, _args = resolve_service(request, path)
    return fill(
        DEVICE_DOCKER,
        name=name,
        description=description,
        image_ref=image_ref(image, tag),
        port=port,
    )


def render_profile(request: str, path: str) -> str:
    """Device manifest when the request names a device, native profile otherwise."""
    kind = device_kind(request)
    if kind:
        return render_device(request, path, kind)
    return render_native(request, path)
