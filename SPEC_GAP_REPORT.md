# MerchantOS final pass: status by checklist section (12 Nov 2026)

Legend: IMPLEMENTED = code exists. VERIFIED = tests ran and passed. LIVE = deployed and confirmed.
In this environment only `py_compile` and the repo's TS/TSX syntax parser were run (both pass).
pytest, npm build, Alembic/Postgres, PayPal Sandbox and Render could not be run. NOTHING below is VERIFIED or LIVE.

## Added in the final passes (IMPLEMENTED)
- Order fulfilment facts (delivered/shipped/hygiene): model, migration 20261112_02, audited PUT endpoint, UI form in case detail.
- Policy result in grid from stored facts (unknown delivery date shows UNKNOWN, never eligible).
- Status/type/policy/AI/decision chips + status quick-filter chips; saved filters.
- Case recommendation now APPROVE / REJECT / EXCHANGE / HOLD_FOR_EVIDENCE with signal strength (rule checks passed, explicitly not a probability), reasons, and shown expected-loss maths.
- Evidence-mismatch flag (evidence for a different order or failed integrity status).
- Optional LLM mode: MERCHANTOS_LLM_ENABLED=true + OPENAI_API_KEY. Sends only non-identifying features, enum-constrained, cannot override HOLD/REJECT. Falls back to computed. Label shows the real mode.
- Isolation Forest score alongside z-score (8+ groups).
- PayPal fee line: basis text added from PayPal Merchant Fees terms (no fee to refund; originally paid fees not returned; region-specific).
- tests/test_spec_additions.py (written, NOT run).

## Honest remaining limits
1. Everything above needs CI to pass before it can be called VERIFIED.
2. Complaint clustering embeddings stay in the older intelligence module (optional, privacy-gated); TF-IDF is the default.
3. Charts are hand-drawn inline bars, not a chart library.
4. Deployed Render service was an older build on 12 Nov (/health had no commit/uptime). Redeploy, then check /api/health and /proof.
5. PayPal Sandbox refund, workflow run ID and demo-video evidence require your accounts.
6. PayPal fee terms differ by country/product (e.g. Braintree); confirm for your account.
