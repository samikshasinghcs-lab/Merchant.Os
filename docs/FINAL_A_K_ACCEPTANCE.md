# Final A–K acceptance checklist

Use `RELEASE_AUDIT.md` as the current implementation/verification report. The status vocabulary is strict:

- **Implemented:** code exists.
- **Verified:** automated or provider test evidence demonstrates it works.
- **Live:** deployed and confirmed by the provider.

Do not promote an item from Implemented to Verified or Live based only on a visible button or source file.

| Area | Evidence to inspect |
|---|---|
| A Global layout | `frontend/src/App.tsx`, responsive CSS, `/api/health`, `/proof` |
| B Cases grid | `frontend/src/pages/FinancialLifecycle.tsx`, AG Grid columns, CSV export and summary cards |
| C Case detail | Case detail API, case-specific evidence events, upload integrity, sticky reason-gated decision controls |
| D Policy | `POST /api/v1/financial-lifecycle/policy/assess`, deterministic rules and audited overrides |
| E P&L | Order costs/COGS, configurable recovery, supplier credit, repair, fee input, write-off and roll-ups |
| F Insights | Batch lift, Fisher exact p-value, repeat-returner signals, reason costs, batch/week charts and non-causal disclosure |
| G AI/deep tech | Computed case recommendation, expected-loss estimates, optional embeddings with TF-IDF fallback, z-score anomaly signals and perceptual image hashing |
| H PayPal | Existing reconciliation, independent maker-checker approval, idempotency and provider-confirmed Sandbox execution |
| I Render | Health commit/service/uptime and persisted `run_resolution_pipeline` run ID |
| J Proof | Authenticated `/proof` page/API, latest refund, workflow reference, last 10 audit entries and disclosures |
| K Security | Tenant authentication, role checks, maker-checker, append-only DB triggers, private evidence limits and tenant isolation |

See the release audit for items that still require frontend build, PostgreSQL, PayPal Sandbox or live Render evidence.
