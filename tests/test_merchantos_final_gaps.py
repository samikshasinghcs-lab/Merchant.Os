import sys
import types
import numpy as np
import pytest
from fastapi import HTTPException


def test_tenant_clustering_uses_tfidf_fallback_without_opt_in(monkeypatch):
    from app.tenant_clustering import cluster_reviews
    monkeypatch.delenv("MERCHANTOS_LOCAL_EMBEDDINGS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", raising=False)
    result = cluster_reviews([
        {"id": "1", "text": "package arrived damaged and broken"},
        {"id": "2", "text": "the package is damaged and broken"},
        {"id": "3", "text": "customer support was helpful and kind"},
    ], threshold=0.2)
    assert result["method"] == "tfidf_cosine_fallback"
    assert result["review_count"] == 3
    assert result["clusters"]
    assert "not proof" in result["caveat"]


def test_tenant_clustering_uses_local_embeddings_when_enabled(monkeypatch):
    from app.tenant_clustering import cluster_reviews
    class FakeModel:
        def __init__(self, name): self.name = name
        def encode(self, texts, normalize_embeddings=True):
            return np.asarray([[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]], dtype=float)
    fake = types.SimpleNamespace(SentenceTransformer=FakeModel)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    monkeypatch.setenv("MERCHANTOS_LOCAL_EMBEDDINGS", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = cluster_reviews([
        {"id": "1", "text": "package damaged"},
        {"id": "2", "text": "parcel broken"},
        {"id": "3", "text": "helpful support"},
    ], threshold=0.9)
    assert result["method"].startswith("local_embeddings:")
    assert result["review_count"] == 3


def test_every_financial_lifecycle_route_depends_on_principal():
    from fastapi.routing import APIRoute
    from app.financial_lifecycle import router, principal
    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert routes
    unprotected = [r.path for r in routes if not any(d.call is principal for d in r.dependant.dependencies)]
    assert unprotected == []


def test_evidence_file_count_limit_is_enforced():
    from app.financial_lifecycle import enforce_evidence_capacity, MAX_CASE_EVIDENCE_FILES
    enforce_evidence_capacity(MAX_CASE_EVIDENCE_FILES - 1)
    with pytest.raises(HTTPException) as exc:
        enforce_evidence_capacity(MAX_CASE_EVIDENCE_FILES)
    assert exc.value.status_code == 409


def test_evidence_multipart_body_limit_allows_file_and_form_overhead():
    from app.main import _api_body_limit
    assert _api_body_limit("/api/v1/financial-lifecycle/cases/123/evidence") == 12 * 1024 * 1024
    assert _api_body_limit("/api/v1/financial-lifecycle/cases/123/detail") == 2 * 1024 * 1024


def test_render_resolution_pipeline_is_deterministic_and_never_moves_money():
    from app.resolution_pipeline import build_resolution_pipeline
    result = build_resolution_pipeline(
        [{"id":"T-1","customer":"C-1","product":"P-1","amount":12.0,
          "status":"captured","created_at":"2026-11-12T10:00:00Z"}],
        [{"event_type":"CASE_CREATED","payload":{"case_id":"C-1"}}],
        100.0, 500.0, "run-test-1",
    )
    assert result["workflow"] == "run_resolution_pipeline"
    assert result["run_id"] == "run-test-1"
    assert result["financial_action"] == "NONE"
    assert "anomalies" in result and "graph" in result and "simulation" in result and "audit" in result


def test_financial_lifecycle_uses_canonical_render_sdk_and_task_name():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    lifecycle = (root / "app/financial_lifecycle.py").read_text()
    workflow = (root / "app/render_workflows.py").read_text()
    assert "from render import RenderAsync" in lifecycle
    assert 'name="run_resolution_pipeline"' in workflow
    assert "from render_sdk import RenderAsync" not in lifecycle
