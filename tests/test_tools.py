import pytest

from agent.templates import render_profile
from agent.tools.actions import strip_fences, write_path
from agent.tools.files import describe_yaml, format_report
from agent.tools.ide_client import WriteFileError
from agent.tools.planner import clean_path, fallback_plan, loose_plan


@pytest.mark.parametrize(
    "text, planned, path",
    [
        # Generic names chosen by the model become the service name...
        ("Create a deployment YAML for a service using the nginx Docker image", "deployment.yaml", "nginx.yaml"),
        ("Create a deployment YAML for a service using the nginx Docker image", "service.yaml", "nginx.yaml"),
        ("write a manifest for ghcr.io/acme/api:2.1", "manifest.yaml", "api.yaml"),
        ("create an application profile for redis", "app.yaml", "redis.yaml"),
        # ...but a name the user gave is kept.
        ("Deploy nginx:1.27 to a phone as phone-nginx.yaml", "phone-nginx.yaml", "phone-nginx.yaml"),
        ("create app.yaml for redis", "app.yaml", "app.yaml"),
        ("create demo/web.yaml with postgres", "demo/web.yaml", "demo/web.yaml"),
        ("make me a yaml", "app.yaml", "app.yaml"),
    ],
)
def test_write_path(text, planned, path):
    assert write_path(text, planned) == path


@pytest.mark.parametrize(
    "text, plan",
    [
        ("delete a.yaml", ("delete", "a.yaml")),
        ("borra a.yaml", ("delete", "a.yaml")),
        ("is x.yml valid", ("validate", "x.yml")),
        ("show nginx.yaml", ("read", "nginx.yaml")),
        ("muestra nginx.yaml", ("read", "nginx.yaml")),
        ("make an nginx service", ("write", "nginx.yaml")),
        ("make me something", ("write", "app.yaml")),
    ],
)
def test_fallback_plan(text, plan):
    assert fallback_plan(text) == plan


def test_loose_plan_reads_tool_calls_written_as_text():
    assert loose_plan('{"name":"plan_ide_action","parameters":{"op":"write","path":"a.yaml"}}') == ("write", "a.yaml")
    assert loose_plan('x {"op":"delete_file","path":"b.yaml"} y') == ("delete", "b.yaml")
    assert loose_plan("nothing here") is None


def test_clean_path_keeps_paths_inside_the_workspace():
    assert clean_path("/x/./b.yaml") == "x/b.yaml"
    assert clean_path("`c.yaml`") == "c.yaml"
    with pytest.raises(WriteFileError):
        clean_path("../etc/passwd")


def test_strip_fences():
    assert strip_fences("```yaml\napplicationProfile: x\n```") == "applicationProfile: x"
    assert strip_fences("Sure:\napiVersion: v1\nkind: X") == "apiVersion: v1\nkind: X"


def test_describe_yaml_says_what_will_be_lost():
    native = render_profile("deploy nginx:1.27", "nginx.yaml")
    assert describe_yaml(native).startswith("native application profile, image nginx:1.27, ")
    assert describe_yaml(native, spanish=True).startswith("perfil de aplicación nativa, imagen nginx:1.27, ")
    device = render_profile("Deploy nginx:1.27 to a phone", "phone.yaml")
    assert describe_yaml(device).startswith("device manifest, image nginx:1.27, ")


def test_format_report():
    assert format_report({"valid": True}) == "Validation passed."
    assert format_report({"valid": True}, spanish=True) == "La validación es correcta."
    report = {"valid": False, "errors": [{"field": "spec.port", "message": "required"}]}
    assert format_report(report) == "Validation failed:\n- spec.port: required"
