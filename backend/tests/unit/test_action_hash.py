from app.core.security import compute_action_hash
from app.schemas.approval import CanonicalAction


def _action(**kw) -> CanonicalAction:
    base = dict(tool="email.send", arguments={"a": 1, "b": 2}, recipient="x@example.com", plan_version=3)
    base.update(kw)
    return CanonicalAction(**base)


def test_hash_is_prefixed_sha256():
    h = compute_action_hash(_action())
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_argument_order_does_not_change_hash():
    a = _action(arguments={"a": 1, "b": 2})
    b = _action(arguments={"b": 2, "a": 1})
    assert compute_action_hash(a) == compute_action_hash(b)


def test_recipient_change_changes_hash():
    a = _action(recipient="x@example.com")
    b = _action(recipient="y@example.com")
    assert compute_action_hash(a) != compute_action_hash(b)


def test_plan_version_change_changes_hash():
    a = _action(plan_version=3)
    b = _action(plan_version=4)
    assert compute_action_hash(a) != compute_action_hash(b)


def test_tool_change_changes_hash():
    a = _action(tool="email.send")
    b = _action(tool="email.send.mock")
    assert compute_action_hash(a) != compute_action_hash(b)
