"""Opt-in live Render Workflow smoke test; never runs in ordinary CI."""
import json, os, urllib.request, urllib.error
import pytest

BASE = os.getenv("MERCHANTOS_LIVE_BASE_URL")
TOKEN = os.getenv("MERCHANTOS_LIVE_TOKEN")
CASE_ID = os.getenv("MERCHANTOS_LIVE_CASE_ID")
pytestmark = pytest.mark.skipif(not all([BASE, TOKEN, CASE_ID]), reason="Live Render workflow credentials/case are not configured")


def call(path, method="GET"):
    req = urllib.request.Request(BASE.rstrip("/") + path, method=method, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def test_render_workflow_runs_and_is_visible_in_proof():
    status, health = call("/api/health")
    assert status == 200 and health.get("status") == "ok"
    assert health.get("commit") not in (None, "unknown")
    status, run = call(f"/api/v1/financial-lifecycle/cases/{CASE_ID}/run-workflow", "POST")
    assert status == 200, run
    assert run.get("run_id") and run.get("financial_action") == "NONE"
    status, proof = call("/api/v1/financial-lifecycle/proof")
    assert status == 200
    assert proof.get("latest_workflow", {}).get("run_id") == run["run_id"]
