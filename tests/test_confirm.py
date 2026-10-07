import pytest

from agent.tools.confirm import cancel_pending, has_pending, interpret_confirmation, pending


@pytest.mark.parametrize(
    "text, decision",
    [
        ("yes", True),
        ("Yes!", True),
        ("yes please", True),
        ("do it", True),
        ("sí", True),
        ("¡sí!", True),
        ("si", True),
        ("vale", True),
        ("sí, bórralo", True),
        ("no", False),
        ("no thanks", False),
        ("No gracias", False),
        ("cancela", False),
        ("si quieres", None),  # "if you want": not a yes
        ("maybe", None),
        ("What is HyperAI?", None),
    ],
)
def test_yes_and_no_are_read_in_code(text, decision):
    assert interpret_confirmation(text) is decision


def test_cancel_pending_removes_the_action():
    pending["u1"] = {"op": "delete", "path": "a.yaml"}
    assert has_pending("u1")
    assert cancel_pending("u1") == {"op": "delete", "path": "a.yaml"}
    assert not has_pending("u1")
    assert cancel_pending("u1") is None
