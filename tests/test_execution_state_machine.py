import pytest

from app.execution_state_machine import (
    EXECUTION_STATES,
    InvalidExecutionTransition,
    transition_execution,
    validate_transition,
)


@pytest.mark.parametrize("current,target", [
    ("RESERVED", "SUBMITTED"),
    ("RESERVED", "SUCCEEDED"),
    ("RESERVED", "FAILED"),
    ("RESERVED", "UNKNOWN"),
    ("SUBMITTED", "RECONCILING"),
    ("SUBMITTED", "SUCCEEDED"),
    ("SUBMITTED", "FAILED"),
    ("SUBMITTED", "UNKNOWN"),
    ("UNKNOWN", "RECONCILING"),
    ("RECONCILING", "SUBMITTED"),
    ("RECONCILING", "SUCCEEDED"),
    ("RECONCILING", "FAILED"),
    ("RECONCILING", "UNKNOWN"),
])
def test_documented_transitions_are_allowed(current, target):
    validate_transition(current, target)


@pytest.mark.parametrize("current,target", [
    ("UNKNOWN", "RESERVED"),
    ("UNKNOWN", "SUBMITTED"),
    ("SUCCEEDED", "SUBMITTED"),
    ("SUCCEEDED", "UNKNOWN"),
    ("FAILED", "RESERVED"),
    ("FAILED", "SUCCEEDED"),
    ("RESERVED", "RESERVED"),
    ("SUBMITTED", "RESERVED"),
    ("NOT_A_STATE", "SUCCEEDED"),
    ("RESERVED", "NOT_A_STATE"),
])
def test_unsafe_or_unknown_transitions_are_rejected(current, target):
    with pytest.raises(InvalidExecutionTransition):
        validate_transition(current, target)


def test_transition_updates_execution_only_after_validation():
    class Execution:
        status = "RESERVED"

    execution = Execution()
    transition_execution(execution, "SUBMITTED")
    assert execution.status == "SUBMITTED"
    with pytest.raises(InvalidExecutionTransition):
        transition_execution(execution, "RESERVED")
    assert execution.status == "SUBMITTED"


def test_state_set_is_explicit_and_contains_no_legacy_success_alias():
    assert EXECUTION_STATES == {
        "RESERVED", "SUBMITTED", "RECONCILING", "SUCCEEDED", "FAILED", "UNKNOWN"
    }
