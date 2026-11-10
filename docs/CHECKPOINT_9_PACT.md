# Checkpoint 9 — PACT Commercial Trust Intelligence

## Implemented
- Agreement draft creation and deterministic natural-language extraction baseline.
- Structured deliverables and acceptance criteria.
- Explicit milestone allocations with exact total reconciliation when supplied.
- Version 1 snapshots and version increments after mutually approved scope changes.
- Two-party agreement approval: named freelancer AND named customer must approve the same version.
- Scope-change requests with explainable lexical overlap classification; two-party approval.
- Milestone evidence submission using registered evidence IDs.
- Deterministic evidence-to-criterion keyword coverage report, explicitly not a proof of completion.
- Customer-only milestone acceptance/rejection.
- Descriptive freelancer/customer operational indicators, no composite trust score.
- PayPal AUTHORIZE order creation, authorization and milestone capture adapter routes restricted to Sandbox.
- Capture is gated on customer acceptance; local PAID is set only when PayPal reports a COMPLETED capture.

## API
- `POST /api/pact/agreements`
- `GET /api/pact/agreements`
- `GET /api/pact/agreements/{agreement_id}`
- `POST /api/pact/agreements/{agreement_id}/approve`
- `GET /api/pact/agreements/{agreement_id}/versions`
- `POST /api/pact/agreements/{agreement_id}/scope-changes`
- `POST /api/pact/scope-changes/{change_id}/approve`
- `POST /api/pact/agreements/{agreement_id}/milestones/{milestone_id}/evidence`
- `POST /api/pact/agreements/{agreement_id}/milestones/{milestone_id}/review`
- `POST /api/pact/agreements/{agreement_id}/milestones/{milestone_id}/payment/authorize-order`
- `POST /api/pact/agreements/{agreement_id}/milestones/{milestone_id}/payment/authorize`
- `POST /api/pact/agreements/{agreement_id}/milestones/{milestone_id}/payment/capture`
- `GET /api/pact/indicators`

## Workflow
1. Create an agreement draft. If milestones are supplied, each needs a positive amount and acceptance criteria; allocations must sum exactly to total.
2. Both named parties separately approve. Agreement becomes ACTIVE only after both approvals.
3. Submit a scope-change request. Lexical classification is a triage hint, not an AI legal conclusion. Both parties approve to increment agreement version.
4. Freelancer submits evidence IDs already registered in the Evidence Vault.
5. Customer accepts or rejects the milestone.
6. For Sandbox payment coordination, create AUTHORIZE order, buyer approves PayPal order, call authorize, and capture only after customer accepts milestone.

## Explicit limitations / safety
- Natural-language extraction is a deterministic baseline, not LLM extraction and not legal advice. Ambiguities are surfaced; parties must review.
- If milestone payment amounts are not provided, draft milestone amounts remain zero and cannot be authorized. Do not invent allocations.
- Evidence criteria checks are keyword coverage only, not verification that work is complete, correct, original or authentic.
- Party-name matching is workflow-level validation, NOT authentication. This build has no secure user login, verified party identity, tenant isolation or production authorization controls.
- PayPal authorization is a temporary hold, not escrow. Authorization validity windows and capture eligibility apply; do not promise funds are reserved indefinitely.
- Sandbox calls have not been verified against real credentials in this checkpoint. Tests mock provider calls where applicable.
- No live payment execution is enabled by these PACT routes. They reject requests unless `DEMO_MODE=false` and `PAYPAL_MODE=sandbox`.
- Production deployment requires secure identity, role/tenant authorization, CSRF protections, webhook verification, concurrency-safe payment state transitions, idempotency reconciliation, database migrations, retention/privacy controls and legal/compliance review.
