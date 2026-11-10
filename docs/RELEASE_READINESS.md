# MerchantOS v5.2 — Production Pilot Release Candidate

## Release decision

**Status: release candidate; deployment is gated on environment readiness.** This is not a production SaaS certification and is not multi-tenant. It is a single-merchant, PayPal-Sandbox-only pilot package. Live PayPal execution remains disabled.

The codebase still has legacy merchant-domain tables in SQLite while identity and selected domain/event data use PostgreSQL. The deployment blueprint therefore mounts a persistent disk for the SQLite pilot data and explicitly acknowledges the single-merchant restriction. Do not onboard a second merchant or treat this as a multi-tenant release.

## Release hardening in this candidate

- Added `/ready` readiness endpoint with fail-closed checks for authentication, JWT secret strength, demo mode, Sandbox-only PayPal configuration, disabled financial execution, PostgreSQL identity database, persistent SQLite pilot storage, single-tenant acknowledgement, HTTPS public URL, Render Workflows credentials, callback secret strength and PayPal Sandbox credentials.
- Kept `/health` as a liveness-only endpoint; it does not imply integrations are ready.
- Added standard response security headers (nosniff, frame denial, referrer policy, permissions policy, HSTS on HTTPS).
- Updated Render blueprint to use `/ready`, set production pilot flags, disable demo mode, and mount the legacy SQLite domain store on `/var/data`.
- Added automated tests for readiness success/failure paths.

## Required Render environment configuration

The blueprint generates `JWT_SECRET_KEY`. Configure the remaining `sync: false` values in Render before deployment:

- `PUBLIC_APP_URL` — final HTTPS service URL.
- `RENDER_API_KEY` and `WORKFLOW_SERVICE_SLUG` — actual Render Workflows service credentials/name.
- `MERCHANTOS_WORKFLOW_SHARED_SECRET` — unique random value, at least 32 characters; set the same value on API and Workflow services.
- `MERCHANTOS_CREDENTIALS_KEY` — valid Fernet key for encrypted merchant credentials (validated by `/ready`).
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` — PayPal Sandbox app values only.

Do not put secrets in the repository or ZIP. Do not set `PAYPAL_MODE=live` or `PAYPAL_EXECUTION_ENABLED=true`.

## Verification performed in the build environment

- Python test suite: see `RELEASE_TEST_REPORT.txt` generated with this package.
- Python compile check: see `RELEASE_TEST_REPORT.txt`.
- Frontend build: status recorded in `RELEASE_TEST_REPORT.txt` if Node dependencies are available.

## Explicitly not certified / blockers to general production

1. Main merchant-domain data still uses SQLite and is not tenant-scoped; PostgreSQL RLS does not protect those legacy tables.
2. End-to-end webhook delivery through a real PayPal Sandbox app and Render Workflows was not possible without merchant-owned credentials and deployment.
3. A real PayPal Sandbox refund/dispute round trip must be re-run after deployment; no live-money test is authorized.
4. Security review, penetration testing, dependency vulnerability scanning, backup/restore rehearsal, monitoring/alerting, and incident-response exercises remain required.
5. Email verification, MFA for financial approvals, token rotation/revocation, full per-route permission matrix, and private object storage/malware scanning remain incomplete.
6. Sponsor SDK entitlements and live APIMatic/AG Grid/Bryntum/Channel3 usage must be verified against actual accounts and licenses; dependency presence alone is not proof of activation.

## Deployment gate

Render's health check targets `/ready`. The service should not be considered ready until every check passes. A passing readiness report only certifies the configured single-merchant Sandbox pilot envelope; it does not waive the blockers above.

The application startup lifespan now refuses to start in `APP_ENV=production` unless every readiness check passes. Sample seed data is not inserted when `DEMO_MODE=false`; `SEED_DEMO_DATA` is also required to remain false in the production pilot.
