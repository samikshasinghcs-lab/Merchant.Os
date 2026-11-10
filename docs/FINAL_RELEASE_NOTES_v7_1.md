# MerchantOS v7.1 — Final polish release

## Included

- PostgreSQL RLS migration for 14 tenant-owned operational tables, with `ENABLE` + `FORCE ROW LEVEL SECURITY`, default-deny tenant policy, and `USING` + `WITH CHECK`.
- Narrow SELECT-only hashed-token lookup policies for webhook routing and invitation acceptance; application code establishes transaction-local token context and derives tenant context from the matched invitation record before its one-time update.
- Cloudflare Hyperdrive transaction-context deployment guide in `SECURITY_FINAL_v7_1.md`.
- PostgreSQL catalog verifier: `scripts/verify_postgres_rls.py`.
- Bounded, provenance-labelled review context for the optional LLM explanation path; no tools are exposed, model output is plain-text-only, bounded, and advisory.
- Prompt-injection regression fixtures for hostile customer review content.
- One-shot operational signal sweep and chart-bar entrance animation on the existing marketing preview, with reduced-motion behavior.

## Verification performed in this environment

- `python -m pytest -q`: **98 passed, 1 skipped**.
- `python -m compileall -q app alembic scripts`: passed.
- Python syntax compilation for the migration and RLS verifier: passed.
- All 14 RLS target tables were checked against SQLAlchemy metadata; each has a non-null `tenant_id` column.
- Frontend production build was attempted but could not complete because `frontend/node_modules` is absent; TypeScript reported unresolved React, router, icon and JSX type dependencies. Install dependencies in the deployment build environment and run `npm install && npm run build`.

## Not verified / not claimed

- No PostgreSQL instance was available for applying the migration or testing RLS behavior.
- No Cloudflare Worker, Hyperdrive binding, Access policy, KV/R2/cache or queue configuration was deployed or tested.
- No two-tenant pooled-connection isolation test was run.
- No browser screenshot, interaction, responsive, accessibility or performance QA was run.
- No deployment or production service was changed from this environment.
- Legacy SQLite business routes and evidence storage remain outside PostgreSQL RLS. Keep multi-tenant mode disabled and retain the single-merchant pilot restriction.
