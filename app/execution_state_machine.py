"""Explicit, fail-closed lifecycle for provider-side financial executions.

A provider acknowledgement (SUBMITTED) is deliberately distinct from a
confirmed financial outcome (SUCCEEDED). UNKNOWN is never automatically retried.
"""
from __future__ import annotations

from dataclasses import dataclass


EXECUTION_STATES = frozenset({
    "RESERVED", "SUBMITTED", "RECONCILING", "SUCCEEDED", "FAILED", "UNKNOWN",
})

# Terminal states are immutable. UNKNOWN can only move into an explicit
# reconciliation path; it cannot be reset to RESERVED or blindly resubmitted.
_ALLOWED_TRANSITIONS = {
    "RESERVED": frozenset({"SUBMITTED", "SUCCEEDED", "FAILED", "UNKNOWN", "RECONCILING"}),
    "SUBMITTED": frozenset({"RECONCILING", "SUCCEEDED", "FAILED", "UNKNOWN"}),
    "UNKNOWN": frozenset({"RECONCILING"}),
    "RECONCILING": frozenset({"SUBMITTED", "SUCCEEDED", "FAILED", "UNKNOWN"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset(),
}


class InvalidExecutionTransition(ValueError):
    """Raised when an execution attempts an illegal lifecycle transition."""


def validate_transition(current: str, target: str) -> None:
    current = str(current or "").upper()
    target = str(target or "").upper()
    if current not in EXECUTION_STATES:
        raise InvalidExecutionTransition(f"Unknown current execution state: {current or '<empty>'}")
    if target not in EXECUTION_STATES:
        raise InvalidExecutionTransition(f"Unknown target execution state: {target or '<empty>'}")
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidExecutionTransition(f"Illegal execution transition: {current} -> {target}")


def transition_execution(execution, target: str) -> None:
    """Validate and apply a transition to a FinancialExecution-like object."""
    validate_transition(execution.status, target)
    execution.status = target.upper()
