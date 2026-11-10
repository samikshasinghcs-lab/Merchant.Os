# MerchantOS — Phase 2: Event-driven intelligence architecture

**Build status:** implemented locally; unit suite passes. Render deployment and real PayPal Sandbox webhook delivery remain unverified external steps.

## Product architecture decision

MerchantOS is a modular merchant-operations intelligence platform. Its MVP is the merchant investigation and resolution workflow. It does not become a general-purpose autonomous procurement or commerce agent. PACT remains a later commercial-trust extension.

**Operating principle:** AI interprets → deterministic systems validate → humans authorize → PayPal executes → audit remembers.

## Event-driven operating loop

1. **Receive:** PayPal sends a webhook to `/api/paypal/webhooks/receive`.
2. **Authenticate:** MerchantOS verifies the PayPal transmission signature against the configured webhook ID and Sandbox credentials.
3. **Minimize:** `sanitize_paypal_event` retains only event identity/type, timestamps, resource identity/status, and amount/currency. Payer and shipping PII are discarded.
4. **Inbox/idempotency:** The event ID is the primary key in `paypal_webhook_events`. Duplicate events already queued or classified are acknowledged without dispatching a second workflow. A failed dispatch remains `RECEIVED` and can be retried.
5. **Dispatch:** Render Workflows receives a stable idempotency key derived from the PayPal event ID.
6. **Classify:** `workflow_engine.py` maps supported PayPal event types to a deterministic reconciliation work item. Unknown event types are quarantined as `IGNORED_UNSUPPORTED`.
7. **Record:** The private callback requires a constant-time comparison of a 32+ character shared secret and records the work item state and audit event.
8. **Reconcile:** `RECONCILIATION_REQUIRED` means a provider-side read/reconciliation is required before local financial state may change. It does not mean the payment was reconciled or settled.

## Financial write boundary

The workflow processor cannot capture, refund, send invoices, alter vault tokens, or submit dispute evidence. Webhooks are signals, not authoritative permission to mutate local financial state. A later reconciliation worker must fetch the canonical PayPal resource, validate merchant/order/currency/amount/status, apply idempotency and deterministic policy, and create an approval request. A merchant with the required role must approve before a financial write is issued through PayPal.

## Deterministic event routing

| PayPal event | Domain | Work item |
|---|---|---|
| `PAYMENT.CAPTURE.COMPLETED` | Payment | `reconcile_capture` |
| `PAYMENT.CAPTURE.DENIED` | Payment | `reconcile_capture_failure` |
| `PAYMENT.CAPTURE.REFUNDED` | Refund | `reconcile_refund` |
| `PAYMENT.CAPTURE.REVERSED` | Payment | `reconcile_reversal` |
| `CUSTOMER.DISPUTE.CREATED/UPDATED/RESOLVED` | Dispute | `sync_dispute` |
| `INVOICING.INVOICE.PAID/CANCELLED` | Invoice | `reconcile_invoice` |
| Any other event | Unknown | Quarantine; no downstream action |

## Observable execution trace

MerchantOS records event ID, event type, workflow run ID, processing status, domain/action classification, timestamps, and whether reconciliation is required. It does not expose model chain-of-thought. Logs should never include credentials, payer email, shipping address, raw webhook payloads, or card data.

## State semantics

- `RECEIVED`: signature verified and sanitized; awaiting dispatch or retry.
- `QUEUED`: Render accepted the idempotent task.
- `RECONCILIATION_REQUIRED`: supported event classified; provider read/reconciliation is the next step. Not a completed payment-state mutation.
- `IGNORED_UNSUPPORTED`: event is not in the explicit allowlist; no action taken.

## Verification performed

- `pytest -q`: **50 passed**.
- Added deterministic routing, unsupported-event quarantine, event identity validation, and no-financial-write assertions.
- Existing test suite remains green.

## Not yet verified

- Render Workflow service release, environment variables, callback reachability, retries, and production observability.
- PayPal Sandbox webhook registration and end-to-end signed delivery.
- Canonical PayPal resource reconciliation after event receipt.
- Live financial operations. All financial writes remain behind existing explicit merchant approval and Sandbox restrictions.
