#!/usr/bin/env python3
"""Fail-closed provider configuration check. Never creates or refunds a payment."""
import os
import sys

def present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())

def main() -> int:
    mode = os.getenv("PAYPAL_MODE", "sandbox").strip().lower()
    checks = {
        "paypal_mode_is_sandbox": mode == "sandbox",
        "paypal_client_id_present": present("PAYPAL_CLIENT_ID"),
        "paypal_client_secret_present": present("PAYPAL_CLIENT_SECRET"),
        "paypal_webhook_id_present": present("PAYPAL_WEBHOOK_ID"),
        "render_api_key_present": present("RENDER_API_KEY"),
        "workflow_service_slug_present": present("WORKFLOW_SERVICE_SLUG"),
        "workflow_shared_secret_32_chars": len(os.getenv("MERCHANTOS_WORKFLOW_SHARED_SECRET", "")) >= 32,
        "public_app_url_https": os.getenv("PUBLIC_APP_URL", "").startswith("https://"),
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "MISSING/FAIL") + " " + name)
    print("No network call was made. No payment was created, captured, or refunded.")
    return 0 if all(checks.values()) else 2

if __name__ == "__main__":
    sys.exit(main())
