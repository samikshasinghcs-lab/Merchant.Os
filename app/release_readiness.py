"""Fail-closed deployment readiness checks for the single-merchant Sandbox pilot.

This is deliberately not a production SaaS certification. Legacy merchant-domain
records remain in SQLite, so only one merchant workspace is supported.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse


def _truthy(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def readiness_report() -> dict:
    production = os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    if not production:
        check("environment", True, "Non-production environment; production gates are not active.")
        return {"ready": True, "environment": "development", "release_scope": "local development only", "checks": checks}

    check("authentication", _truthy("AUTH_REQUIRED"), "AUTH_REQUIRED must be true.")
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    check("jwt_secret", len(jwt_secret) >= 32 and jwt_secret not in {
        "local-development-secret-change-this-before-deploying",
        "replace-with-a-long-random-secret-before-deploying",
    }, "Use a unique secret of at least 32 characters.")
    check("demo_mode", not _truthy("DEMO_MODE"), "DEMO_MODE must be false for the Sandbox pilot.")
    check("demo_seed", not _truthy("SEED_DEMO_DATA"), "SEED_DEMO_DATA must be false; production must not be populated with sample merchant records.")
    check("paypal_environment", os.getenv("PAYPAL_MODE", "sandbox").lower() == "sandbox",
          "This release is Sandbox-only; live PayPal is not supported.")
    check("financial_execution", not _truthy("PAYPAL_EXECUTION_ENABLED"),
          "Direct financial execution must remain disabled in this release candidate.")
    db_url = os.getenv("DATABASE_URL", "")
    check("identity_database", db_url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")),
          "Production pilot identity database must be PostgreSQL.")
    data_path = os.getenv("DATABASE_PATH", "")
    check("persistent_domain_storage", os.path.isabs(data_path) and data_path.startswith("/var/data/"),
          "Legacy single-tenant domain SQLite must be on the mounted /var/data persistent disk.")
    check("single_tenant_restriction", _truthy("MERCHANTOS_SINGLE_TENANT_PILOT"),
          "Explicitly acknowledge the single-merchant pilot restriction.")
    evidence_dir = os.getenv("EVIDENCE_UPLOAD_DIR", "")
    evidence_path = os.path.realpath(evidence_dir) if evidence_dir else ""
    static_root = os.path.realpath(os.path.join(os.path.dirname(__file__), "static"))
    try:
        evidence_is_inside_static = bool(evidence_path) and os.path.commonpath([static_root, evidence_path]) == static_root
    except ValueError:
        evidence_is_inside_static = True
    evidence_is_symlink = bool(evidence_dir) and os.path.islink(evidence_dir)
    check("private_evidence_storage_path", bool(evidence_path) and os.path.isabs(evidence_dir)
          and not evidence_is_inside_static and not evidence_is_symlink,
          "Set EVIDENCE_UPLOAD_DIR to an absolute private persistent path outside the web-served static directory; the configured directory must not be a symlink.")
    if evidence_path and os.path.isdir(evidence_path):
        try:
            evidence_mode = os.stat(evidence_path).st_mode
            private_permissions = (evidence_mode & 0o077) == 0
        except OSError:
            private_permissions = False
        check("private_evidence_storage_permissions", private_permissions,
              "Existing evidence storage must not grant group or world permissions (recommended mode 0700).")
    else:
        check("private_evidence_storage_permissions", True,
              "Storage permissions will be enforced as 0700 when the evidence directory is created.")
    external_review_processing = _truthy("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING")
    if external_review_processing:
        check("external_review_processing_ack", _truthy("MERCHANTOS_EXTERNAL_REVIEW_DPA_ACK")
              and _truthy("MERCHANTOS_EXTERNAL_REVIEW_REDACTION_ACK"),
              "External review processing requires documented processor/DPA review and data-redaction approval.")
    else:
        check("external_review_processing", True, "External review text is not sent to hosted embedding or LLM APIs.")
    public_url = os.getenv("PUBLIC_APP_URL", "")
    parsed = urlparse(public_url)
    check("https_public_url", parsed.scheme == "https" and bool(parsed.netloc),
          "PUBLIC_APP_URL must be a public HTTPS URL.")
    check("workflow_credentials", bool(os.getenv("RENDER_API_KEY")) and bool(os.getenv("WORKFLOW_SERVICE_SLUG")),
          "Render Workflows API key and service slug are required for webhook processing.")
    shared = os.getenv("MERCHANTOS_WORKFLOW_SHARED_SECRET", "")
    check("workflow_shared_secret", len(shared) >= 32,
          "Use a unique workflow callback secret of at least 32 characters.")
    check("paypal_sandbox_credentials", bool(os.getenv("PAYPAL_CLIENT_ID")) and bool(os.getenv("PAYPAL_CLIENT_SECRET")),
          "Configure PayPal Sandbox credentials; never use live credentials.")
    check("paypal_webhook_id", bool(os.getenv("PAYPAL_WEBHOOK_ID")),
          "Configure the PayPal Sandbox webhook ID for signature verification.")
    credential_key = os.getenv("MERCHANTOS_CREDENTIALS_KEY", "")
    try:
        from cryptography.fernet import Fernet
        Fernet(credential_key.encode("ascii"))
        credential_key_valid = True
    except Exception:
        credential_key_valid = False
    check("credential_encryption_key", credential_key_valid,
          "MERCHANTOS_CREDENTIALS_KEY must be a valid Fernet key.")

    return {
        "ready": all(item["passed"] for item in checks),
        "environment": "production",
        "release_scope": "single-merchant, PayPal-Sandbox-only pilot; not multi-tenant SaaS",
        "financial_execution": "disabled",
        "checks": checks,
    }
