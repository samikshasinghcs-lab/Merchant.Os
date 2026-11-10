"""Tenant-scoped PayPal REST adapter. Never reads global merchant credentials."""
from __future__ import annotations
import requests
def get_paypal_credentials(tenant_id, environment):
    # Lazy import keeps the adapter independently testable and avoids loading identity
    # dependencies until a real tenant credential lookup is requested.
    from .tenant_operations import get_paypal_credentials as lookup
    return lookup(tenant_id, environment)

class TenantPayPalError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, ambiguous: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.ambiguous = ambiguous

class TenantPayPalAdapter:
    def __init__(self, tenant_id: str, environment: str = "sandbox", *, timeout: int = 20):
        if environment not in {"sandbox", "live"}:
            raise ValueError("PayPal environment must be sandbox or live")
        creds = get_paypal_credentials(tenant_id, environment)
        if not creds:
            raise TenantPayPalError(f"No active PayPal {environment} credentials for this tenant")
        self.tenant_id, self.environment, self.timeout = tenant_id, environment, timeout
        self.client_id, self.client_secret = creds["client_id"], creds["client_secret"]
        self.root = "https://api-m.sandbox.paypal.com" if environment == "sandbox" else "https://api-m.paypal.com"
        self._token = None

    def _access_token(self):
        if self._token:
            return self._token
        try:
            r = requests.post(self.root + "/v1/oauth2/token", auth=(self.client_id, self.client_secret),
                              data={"grant_type": "client_credentials"}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise TenantPayPalError("PayPal OAuth transport failure", ambiguous=True) from exc
        if not r.ok:
            raise TenantPayPalError(f"PayPal OAuth rejected credentials ({r.status_code})", status_code=r.status_code)
        try:
            self._token = r.json()["access_token"]
        except (ValueError, KeyError) as exc:
            raise TenantPayPalError("Malformed PayPal OAuth response", ambiguous=True) from exc
        return self._token

    def _request(self, method, path, *, body=None, request_id=None):
        headers = {"Authorization": "Bearer " + self._access_token(), "Content-Type": "application/json"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        try:
            r = requests.request(method, self.root + path, headers=headers, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            # A write may have committed before the connection failed; GETs are safe reads.
            is_write = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
            raise TenantPayPalError("PayPal transport failure; outcome is unknown" if is_write else "PayPal read transport failure",
                                    ambiguous=is_write) from exc
        try:
            payload = r.json() if r.content else {}
        except ValueError as exc:
            is_write = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
            raise TenantPayPalError("PayPal returned an unreadable response; write outcome is unknown" if is_write else "PayPal returned an unreadable read response",
                                    status_code=getattr(r, "status_code", None), ambiguous=is_write) from exc
        if not r.ok:
            msg = payload.get("message") or payload.get("name") or "PayPal request rejected"
            is_ambiguous = method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and int(r.status_code) >= 500
            raise TenantPayPalError(f"{msg} (HTTP {r.status_code})", status_code=r.status_code, ambiguous=is_ambiguous)
        if method.upper() in {"POST", "PUT", "PATCH"} and not isinstance(payload, dict):
            raise TenantPayPalError("PayPal write returned an unexpected response; outcome is unknown", ambiguous=True)
        return payload

    def get_capture(self, capture_id: str) -> dict:
        return self._request("GET", f"/v2/payments/captures/{capture_id}")

    def refund_capture(self, capture_id: str, amount: str, currency: str, request_id: str) -> dict:
        return self._request("POST", f"/v2/payments/captures/{capture_id}/refund",
            body={"amount": {"value": amount, "currency_code": currency},
                  "note_to_payer": "Merchant-approved refund via MerchantOS"}, request_id=request_id)
