import pytest

from agent.templates.parsing import (
    device_kind,
    extract_image_ref,
    extract_port,
    image_ref,
    resolve_service,
    service_name,
    split_image,
)


@pytest.mark.parametrize(
    "text, port",
    [
        ("nginx on port 8080", 8080),
        ("nginx en el puerto 9000", 9000),
        ("run nginx on 8080", 8080),
        ("expose it at :3000", 3000),
        ("postgres:16 please", 80),  # an image tag, not a port
        ("run on 10 nodes", 80),  # a count, not a port
        ("port 99999", 80),  # out of range
        ("no port here", 80),
    ],
)
def test_extract_port(text, port):
    assert extract_port(text, 80) == port


def test_split_image_adds_the_docker_hub_prefix():
    assert split_image("nginx:1.27") == ("docker.io/library/nginx", "1.27")
    assert split_image("ghcr.io/acme/api") == ("ghcr.io/acme/api", None)


def test_image_ref_shortens_official_images():
    assert image_ref("docker.io/library/nginx", "1.27") == "nginx:1.27"
    assert image_ref("ghcr.io/acme/api", "2.1") == "ghcr.io/acme/api:2.1"


def test_extract_image_ref_skips_generic_words():
    assert extract_image_ref("Deploy nginx:1.27 to a phone") == "nginx:1.27"
    assert extract_image_ref("a service using the nginx Docker image") == "nginx"
    assert extract_image_ref("create a deployment yaml") is None


@pytest.mark.parametrize(
    "text, name",
    [
        ("Create a deployment YAML for a service using the nginx Docker image", "nginx"),
        ("write a manifest for ghcr.io/acme/api:2.1", "api"),
        ("an application profile for redis", "redis"),
        ("make me a yaml", None),
    ],
)
def test_service_name(text, name):
    assert service_name(text) == name


def test_resolve_service_uses_the_catalogue_and_the_port():
    image, tag, entry, port, args = resolve_service("postgres on port 6000", "db.yaml")
    assert (image, tag, entry, port) == ("docker.io/library/postgres", "16", "postgres", 6000)


@pytest.mark.parametrize(
    "text, kind",
    [
        ("flash firmware to an esp32", "esp32"),
        ("install the apk on android", "android"),
        ("deploy nginx to a phone", "docker"),
        ("deploy nginx", None),
    ],
)
def test_device_kind(text, kind):
    assert device_kind(text) == kind
