import re

import pytest

from agent.templates import render_profile

PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


@pytest.mark.parametrize(
    "request_text, path, root",
    [
        ("Create a deployment YAML for a service using the nginx Docker image", "nginx.yaml", "applicationProfile:"),
        ("Deploy nginx:1.27 to a phone on port 8080", "phone.yaml", "apiVersion: hyper.ai/v1"),
        ("install https://x.io/app.apk com.acme.app on android", "android.yaml", "apiVersion: hyper.ai/v1"),
        ("flash https://x.io/fw.bin to an esp32c3 over serial", "esp.yaml", "apiVersion: hyper.ai/v1"),
    ],
)
def test_every_template_is_fully_filled(request_text, path, root):
    yaml = render_profile(request_text, path)
    assert yaml.startswith(root)
    assert not PLACEHOLDER.search(yaml), PLACEHOLDER.findall(yaml)


def test_native_profile_takes_image_tag_and_port_from_the_sentence():
    yaml = render_profile("deploy nginx:1.25 on port 8080", "web.yaml")
    assert 'name: "web"' in yaml
    assert 'uri: "docker.io/library/nginx"' in yaml
    assert 'tag: "1.25"' in yaml
    assert "- port: 8080" in yaml


def test_device_manifest_uses_the_requested_workload():
    assert "kind: DockerImage" in render_profile("Deploy nginx:1.27 to a phone", "p.yaml")
    assert "kind: AndroidApk" in render_profile("an android apk", "a.yaml")
    esp = render_profile("flash https://x.io/fw.bin to an esp32c3 over serial", "e.yaml")
    assert "chip: esp32c3" in esp
    assert "method: serial" in esp
