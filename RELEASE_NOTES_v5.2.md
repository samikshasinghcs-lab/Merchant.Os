# MerchantOS v5.2 — Release Candidate

## Included
- Production readiness gate and `/ready` endpoint.
- Fail-closed application startup for `APP_ENV=production` until required pilot configuration passes.
- No sample merchant seed data in production.
- Security response headers.
- Render blueprint configured for a single-merchant Sandbox pilot with persistent legacy SQLite storage.
- Release readiness and test evidence.

## Verification
- 73 Python tests pass.
- Python compile check passes.
- Render blueprint YAML parses successfully.
- Frontend build was not run: `frontend/node_modules` was absent and no package installation was attempted.
- No real PayPal or Render service calls were performed during packaging.

## Release classification
This is a **production-pilot release candidate**, not a general production release. The app remains single-merchant, PayPal Sandbox only, with financial execution disabled. The legacy merchant-domain database has not been migrated to tenant-isolated PostgreSQL. Do not enable live PayPal credentials or onboard multiple merchants.
