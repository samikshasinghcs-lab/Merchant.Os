"""PayPal REST adapter. Real-money actions are disabled by default (DEMO_MODE=true)."""
import requests
from urllib.parse import urlencode
from datetime import datetime, timezone
from .config import DEMO, MODE, CLIENT_ID, CLIENT_SECRET

class PayPalError(Exception):
    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload

def base():
    if MODE == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    if MODE == "live":
        return "https://api-m.paypal.com"
    raise PayPalError("PAYPAL_MODE must be 'sandbox' or 'live'")

def _request(method, path, *, json_body=None, idem=None, params=None):
    access_token = token()
    headers = {"Authorization": "Bearer " + access_token, "Content-Type": "application/json"}
    if idem:
        headers["PayPal-Request-Id"] = idem
    try:
        response = requests.request(method, base() + path, headers=headers,
                                    json=json_body, params=params, timeout=30)
    except requests.RequestException as exc:
        raise PayPalError(f"PayPal network error: {exc}") from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:500]}
    if not response.ok:
        detail = payload.get("message") or payload.get("name") or str(payload)
        raise PayPalError(f"PayPal API error {response.status_code}: {detail}",
                          response.status_code, payload)
    return payload

def token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise PayPalError("PayPal credentials are missing. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env")
    try:
        r = requests.post(base()+"/v1/oauth2/token", auth=(CLIENT_ID, CLIENT_SECRET),
                          data={"grant_type": "client_credentials"}, timeout=20)
    except requests.RequestException as exc:
        raise PayPalError(f"PayPal OAuth network error: {exc}") from exc
    if not r.ok:
        raise PayPalError(f"OAuth error {r.status_code}: {r.text[:300]}", r.status_code)
    try:
        return r.json()["access_token"]
    except (ValueError, KeyError) as exc:
        raise PayPalError("PayPal OAuth response did not contain an access token") from exc

def create_order(amount, currency, description, idem):
    return _request("POST", "/v2/checkout/orders", idem=idem, json_body={
        "intent": "CAPTURE",
        "purchase_units": [{
            "description": description[:127],
            "amount": {"currency_code": currency.upper(), "value": f"{amount:.2f}"}
        }],
        "payment_source": {"paypal": {"experience_context": {
            "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
            "user_action": "PAY_NOW",
            "return_url": "http://localhost:8000/paypal/return",
            "cancel_url": "http://localhost:8000/paypal/cancel"
        }}}
    })

def capture_order(order_id, idem):
    return _request("POST", f"/v2/checkout/orders/{order_id}/capture", idem=idem, json_body={})

def refund(capture_id, amount, currency, idem):
    if DEMO:
        return {"id": "SIM-" + idem[:12], "status": "SIMULATED", "mode": "demo"}
    return _request("POST", f"/v2/payments/captures/{capture_id}/refund", idem=idem,
                    json_body={"amount": {"value": f"{amount:.2f}", "currency_code": currency},
                               "note_to_payer": "Merchant-approved refund via MerchantOS"})


def list_disputes(page_size=20):
    return _request("GET", f"/v1/customer/disputes?page_size={int(page_size)}")

def get_dispute(dispute_id):
    return _request("GET", f"/v1/customer/disputes/{dispute_id}")

def provide_dispute_evidence(dispute_id, evidence_type, notes, file_paths, evidence_info=None):
    """Submit evidence using PayPal's multipart Disputes API. Caller must enforce approval."""
    import os, mimetypes
    access_token = token()
    url = base() + f"/v1/customer/disputes/{dispute_id}/provide-evidence"
    headers = {"Authorization": "Bearer " + access_token}
    evidence = {"evidence_type": evidence_type, "notes": (notes or "")[:2000]}
    if evidence_info:
        evidence["evidence_info"] = evidence_info
    payload = {"evidences": [evidence]}
    files = {"input": (None, __import__('json').dumps(payload), "application/json")}
    opened = []
    try:
        for i, path in enumerate(file_paths, start=1):
            handle = open(path, "rb")
            opened.append(handle)
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            files[f"file{i}"] = (os.path.basename(path), handle, mime)
        response = requests.post(url, headers=headers, files=files, timeout=60)
    except requests.RequestException as exc:
        raise PayPalError(f"PayPal dispute submission network error: {exc}") from exc
    finally:
        for handle in opened:
            handle.close()
    try:
        result = response.json()
    except ValueError:
        result = {"raw": response.text[:1000]}
    if not response.ok:
        detail = result.get("message") or result.get("name") or str(result)
        raise PayPalError(f"PayPal dispute API error {response.status_code}: {detail}", response.status_code, result)
    return result


def create_authorization_order(amount, currency, description, idem):
    return _request("POST", "/v2/checkout/orders", idem=idem, json_body={
        "intent": "AUTHORIZE",
        "purchase_units": [{"description": description[:127],
                            "amount": {"currency_code": currency.upper(), "value": f"{amount:.2f}"}}],
        "payment_source": {"paypal": {"experience_context": {
            "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
            "user_action": "PAY_NOW",
            "return_url": "http://localhost:8000/paypal/return",
            "cancel_url": "http://localhost:8000/paypal/cancel"
        }}}
    })

def authorize_order(order_id, idem):
    return _request("POST", f"/v2/checkout/orders/{order_id}/authorize", idem=idem, json_body={})

def capture_authorization(authorization_id, amount, currency, idem):
    return _request("POST", f"/v2/payments/authorizations/{authorization_id}/capture", idem=idem,
                    json_body={"amount":{"value":f"{amount:.2f}","currency_code":currency.upper()},
                               "final_capture":True})


# Additional PayPal capabilities used by MerchantOS financial operations.
def create_invoice_draft(invoice, idem):
    if not isinstance(invoice, dict) or not isinstance(invoice.get("detail"), dict) or not invoice.get("items"):
        raise PayPalError("Invoice must include detail and a non-empty items array")
    return _request("POST", "/v2/invoicing/invoices", json_body=invoice, idem=idem)

def get_invoice(invoice_id):
    return _request("GET", f"/v2/invoicing/invoices/{invoice_id}")

def send_invoice(invoice_id, idem, *, send_to_recipient=True, send_to_invoicer=False):
    return _request("POST", f"/v2/invoicing/invoices/{invoice_id}/send", idem=idem,
                    json_body={"send_to_recipient": bool(send_to_recipient),
                               "send_to_invoicer": bool(send_to_invoicer)})

def search_transactions(*, start_date, end_date, page_size=50, page=1, transaction_id=None,
                        transaction_status=None, transaction_currency=None):
    params = {"start_date": start_date, "end_date": end_date,
              "page_size": int(page_size), "page": int(page)}
    if transaction_id: params["transaction_id"] = transaction_id
    if transaction_status: params["transaction_status"] = transaction_status
    if transaction_currency: params["transaction_currency"] = transaction_currency.upper()
    return _request("GET", "/v1/reporting/transactions", params=params)

def create_vault_setup_token(customer_id, return_url, cancel_url, idem):
    # Uses PayPal Wallet approval. MerchantOS never receives or stores PAN/CVV.
    payload = {
        "customer": {"merchant_customer_id": customer_id},
        "payment_source": {"paypal": {
            "description": "MerchantOS approved future payments",
            "usage_pattern": "IMMEDIATE",
            "experience_context": {"return_url": return_url, "cancel_url": cancel_url,
                                   "user_action": "CONTINUE"}
        }}
    }
    return _request("POST", "/v3/vault/setup-tokens", json_body=payload, idem=idem)

def get_vault_setup_token(setup_token_id):
    return _request("GET", f"/v3/vault/setup-tokens/{setup_token_id}")

def create_vault_payment_token(setup_token_id, customer_id, idem):
    payload = {"customer": {"merchant_customer_id": customer_id},
               "payment_source": {"token": {"id": setup_token_id, "type": "SETUP_TOKEN"}}}
    return _request("POST", "/v3/vault/payment-tokens", json_body=payload, idem=idem)
