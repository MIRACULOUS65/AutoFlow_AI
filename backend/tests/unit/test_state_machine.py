import pytest

from app.core.errors import AppError, ErrorCode
from app.domain.enums import TaskStatus as T
from app.orchestration import state_machine as sm


@pytest.mark.parametrize(
    "src,dst",
    [
        (T.QUEUED, T.PLANNING),
        (T.PLANNING, T.VALIDATING),
        (T.VALIDATING, T.RUNNING),
        (T.VALIDATING, T.AWAITING_APPROVAL),
        (T.AWAITING_APPROVAL, T.RUNNING),
        (T.RUNNING, T.VERIFYING),
        (T.VERIFYING, T.COMPLETE),
        (T.RUNNING, T.RECOVERY),
        (T.RECOVERY, T.RUNNING),
    ],
)
def test_legal_transitions(src, dst):
    assert sm.can_transition(src, dst)
    assert sm.transition(src, dst) == dst


@pytest.mark.parametrize(
    "src,dst",
    [
        (T.COMPLETE, T.RUNNING),
        (T.COMPLETE, T.CANCELLED),
        (T.FAILED, T.RUNNING),
        (T.CANCELLED, T.RUNNING),
        (T.QUEUED, T.COMPLETE),
    ],
)
def test_illegal_transitions_rejected(src, dst):
    assert not sm.can_transition(src, dst)
    with pytest.raises(AppError) as exc:
        sm.validate_transition(src, dst)
    assert exc.value.code == ErrorCode.INVALID_STATE_TRANSITION


def test_terminal_states_have_no_exits():
    for terminal in (T.COMPLETE, T.FAILED, T.CANCELLED, T.EXPIRED):
        assert sm.is_terminal(terminal)
        assert sm.allowed_from(terminal) == frozenset()


def test_same_state_is_not_a_transition():
    assert not sm.can_transition(T.RUNNING, T.RUNNING)
