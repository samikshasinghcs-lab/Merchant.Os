import pytest
from fastapi import HTTPException

from app.intelligence import RunIn, _SYSTEM_PROMPT, _read_task_token, _task_token, simulate_policy, validate_input


def test_rejects_duplicate_transaction_ids():
    body = RunIn(transactions=[
        {"id":"same","customer":"c1","product":"p","amount":1,"status":"captured","created_at":"2026-01-01T00:00:00Z"},
        {"id":"same","customer":"c2","product":"p","amount":2,"status":"captured","created_at":"2026-01-01T00:01:00Z"},
    ])
    with pytest.raises(HTTPException) as exc:
        validate_input(body)
    assert exc.value.status_code == 422


def test_rejects_unknown_status_and_malformed_timestamp():
    for status, timestamp in [("REFUNDED", "2026-01-01T00:00:00Z"), ("captured", "not-a-date")]:
        body = RunIn(transactions=[{"id":"t1","customer":"c","product":"p","amount":1,"status":status,"created_at":timestamp}])
        with pytest.raises(HTTPException):
            validate_input(body)


def test_prompt_marks_all_fact_values_as_untrusted_and_disables_actions():
    assert "UNTRUSTED DATA" in _SYSTEM_PROMPT
    assert "call tools" in _SYSTEM_PROMPT
    assert "cannot move money" in _SYSTEM_PROMPT


def test_policy_simulation_counts_only_canonical_refund_requested_status():
    txns = [
        {"id":"a","status":"refund_requested","amount":10,"created_at":"2026-01-01T00:00:00Z"},
        {"id":"b","status":"REFUND_REQUESTED","amount":10,"created_at":"2026-01-01T00:00:00Z"},
    ]
    result = simulate_policy(txns, 100, 500)
    assert result["pending"] == 1
    assert result["would_approve"] == ["a"]
