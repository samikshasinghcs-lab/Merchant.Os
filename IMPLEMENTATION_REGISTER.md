# MerchantOS implementation register — v8.0 candidate

Statuses distinguish source presence from runtime operation.

| Area | Status | Evidence / limitation |
|---|---|---|
| FastAPI backend | IMPLEMENTED | Source and automated test suite present. |
| React/Vite frontend | IMPLEMENTED | Source and package manifest present; build not run in this environment. |
| PayPal adapters | IMPLEMENTED | Source and mocked tests present; external Sandbox operation must be verified in the target account. |
| Refund reconciliation | IMPLEMENTED | Route/service source and automated tests present; provider round-trip still requires runtime proof. |
| Financial approvals | IMPLEMENTED | Deterministic controls and tests present; full external workflow proof pending. |
| PostgreSQL tenant foundation | IMPLEMENTED | Models/migrations and RLS artefacts present; legacy domain workflows still include SQLite. |
| Full multi-tenant isolation | IN DEVELOPMENT | Do not enable multi-tenant onboarding until legacy cutover and two-tenant RLS tests pass. |
| Prompt-injection boundary | IMPLEMENTED | Untrusted-content handling and focused regression tests present; broader adversarial review pending. |
| Render workflow integration | IN DEVELOPMENT | Source/configuration present; hosted workflow runtime not verified. |
| AG Grid / Bryntum | IMPLEMENTED | Dependencies declared; frontend build/runtime verification pending. |
| APIMatic | NOT STARTED / USER ACTIVATION REQUIRED | Activation script and instructions only; no successful activation evidence. |
| Vercel frontend | IN DEVELOPMENT | Vite SPA configuration prepared; project/deployment not yet created. |
| Production deployment | NOT STARTED | No deployment evidence in this package. |
| Independent security validation | NOT STARTED | No external penetration test or certification evidence. |

## Release gate

This package is a consolidated GitHub candidate, not a production-readiness certification. Keep `MULTI_TENANT_ENABLED=false`, `PAYPAL_EXECUTION_ENABLED=false` until their respective runtime security and provider tests have passed. Keep PayPal in Sandbox. Never commit secrets or local databases.
