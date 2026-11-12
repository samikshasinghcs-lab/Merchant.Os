from fastapi.routing import APIRoute
from fastapi import HTTPException
import pytest
from app.financial_lifecycle import router, MAX_CASE_EVIDENCE_FILES, MAX_CASE_EVIDENCE_BYTES, validate_case_evidence_limits


def test_every_financial_lifecycle_route_requires_authenticated_principal():
    routes = [route for route in router.routes if isinstance(route, APIRoute)]
    assert routes
    unprotected = [route.path for route in routes if not route.dependant.dependencies]
    assert unprotected == []


def test_case_evidence_upload_limits_are_explicit_and_bounded():
    assert MAX_CASE_EVIDENCE_FILES == 8
    assert MAX_CASE_EVIDENCE_BYTES == 5 * 1024 * 1024
    upload = next(route for route in router.routes if getattr(route, "path", "").endswith("/cases/{case_id}/evidence"))
    assert "POST" in upload.methods
    assert upload.dependant.dependencies


def test_case_evidence_limit_allows_eighth_item_but_blocks_ninth():
    validate_case_evidence_limits(7, 1024)
    with pytest.raises(HTTPException) as error:
        validate_case_evidence_limits(8, 1024)
    assert error.value.status_code == 409


def test_case_evidence_limit_blocks_empty_and_over_5mb_files():
    for size in (0, MAX_CASE_EVIDENCE_BYTES + 1):
        with pytest.raises(HTTPException) as error:
            validate_case_evidence_limits(0, size)
        assert error.value.status_code == 413
