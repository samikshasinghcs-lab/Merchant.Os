# MerchantOS final gap-closure handoff

This archive consolidates the uploaded MerchantOS repository and closes the remaining source-level gaps identified in the A–K review.

## Local verification

- Backend: 289 passed, 5 skipped (`pytest -q -rs`).
- Python compilation: passed.
- Frontend TS/TSX syntax: passed.
- Financial grid acceptance verifier: passed.

## External release gates

The local environment could not resolve the npm registry, so the React/Vite production build could not be run here. GitHub Actions runs the full frontend typecheck/build after upload. Live PostgreSQL/RLS, PayPal Sandbox refund and Render workflow smoke tests are included as opt-in workflow jobs; they require merchant-owned disposable test resources and secrets. No live payment was executed while preparing this archive.

Read `FINAL_GAP_CLOSURE_REPORT.md` and `PROVIDER_VERIFICATION_RUNBOOK.md` before the competition demo. Keep `PAYPAL_MODE=sandbox`; never use live credentials.
