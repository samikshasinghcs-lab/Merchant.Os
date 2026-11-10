# MerchantOS Checkpoint 4 — Customer Resolution Intelligence

## Delivered
- Deterministic category-based resolution recommendations with human-readable rationale.
- Evidence references surfaced in recommendation context through the order relationship.
- Editable empathetic/concise customer message drafts; no outbound messaging integration.
- Resolution lifecycle records with `OPEN`, `CONTACTED`, `RESOLVED`, and `ESCALATED` states.
- One active resolution per review; repeated create requests return the existing active record.
- Merchant notes, audit events, input validation, and terminal-state protection.

## API
- `GET /api/resolutions/recommendation/{review_id}`
- `GET /api/resolutions/message/{review_id}?tone=empathetic|concise`
- `POST /api/resolutions` with `{"review_id":"...", "tone":"empathetic"}`
- `GET /api/resolutions?status=OPEN`
- `PATCH /api/resolutions/{resolution_id}` with `{"status":"CONTACTED", "merchant_note":"..."}`

## Safety boundaries
Recommendations are deterministic triage, not outcome predictions. Message drafts are not sent. Creating/updating a resolution does not issue a refund, submit a dispute, or authorize a financial action. A merchant must inspect the underlying order and evidence and separately approve any financial action.

## Verification
Automated tests: 13 passed. Python compilation and API smoke checks are included in the release verification.
