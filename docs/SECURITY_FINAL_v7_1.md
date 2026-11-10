# MerchantOS v7.1 — Tenant RLS, prompt-injection boundaries & final product finish

## Release scope and truth

This release adds PostgreSQL row-level security (RLS) policies for the tenant-owned PostgreSQL tables, makes the optional review-cluster LLM path treat imported customer text as untrusted data, adds a read-only RLS verification utility, and adds a restrained one-shot motion pass to the existing React landing page.

It does **not** configure a Cloudflare account, create a Worker, provision Hyperdrive, deploy a Worker, or prove production isolation. MerchantOS is still a single-merchant pilot: the legacy business routes and their SQLite data have not been migrated. Keep `MULTI_TENANT_ENABLED=false` and do not enable multi-merchant onboarding.

## PostgreSQL RLS boundary

Alembic revision `20261110_01` bootstraps the declared SQLAlchemy schema (the repository had no prior Alembic revisions) and enables + forces RLS on:

- `merchant_orders`, `merchant_reviews`, `merchant_refunds`, `merchant_disputes`, `merchant_evidence`, `merchant_audit_events`
- `merchant_paypal_credentials`, `paypal_webhook_events`, `paypal_webhook_routes`, `event_execution_traces`
- `pact_party_approvals`, `merchant_invitations`, `financial_approval_requests`, `financial_executions`

Every table receives a default-deny tenant policy equivalent to:

```sql
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')
)
```

`USING` constrains reads, updates and deletes; `WITH CHECK` constrains inserted and updated row ownership. Missing transaction context yields no matching tenant and therefore no access. `FORCE ROW LEVEL SECURITY` subjects the table owner to policy enforcement, but PostgreSQL superusers and roles with `BYPASSRLS` still bypass RLS. The application runtime role must not be superuser and must not have `BYPASSRLS`.

Two tables need narrowly scoped cross-tenant lookups before a tenant context is known: public PayPal webhook route resolution and one-time invitation acceptance. They have additional **SELECT-only** policies that expose only the row whose high-entropy token hash matches a transaction-local `app.webhook_token_hash` or `app.invitation_token_hash`. The corresponding application code sets those values with bound parameters and does not grant general list access. These exceptions are necessary for the documented flows and must remain limited to token-hash equality.

`app.tenant_id` must come from the authenticated principal's active database membership, never a request body, query parameter, header supplied by the browser, queue payload, or model output. `tenant_session()` establishes it with a bound `set_config(..., true)` call in the same SQLAlchemy transaction as the protected query. The `true` argument makes the setting transaction-local, which is important with pooled connections.

### Cloudflare Hyperdrive compatibility

These are native PostgreSQL RLS policies and transaction-local context, so they can be used behind Cloudflare Hyperdrive. Hyperdrive itself is **not** configured in this repository. A future Worker must:

1. Validate the caller's identity and current membership before opening the database transaction.
2. Derive the tenant ID from that verified membership; ignore caller-supplied tenant IDs.
3. Start a transaction on the Hyperdrive connection.
4. Set `app.tenant_id` transaction-locally using a parameterized query (`SELECT set_config('app.tenant_id', $1, true)`).
5. Perform all protected reads/writes in that same transaction and commit/rollback before returning the pooled connection.
6. Never rely on connection-level `SET`, session variables surviving pool reuse, or Hyperdrive cache keys as authorization.

Do not share authenticated responses across tenants in CDN/KV caches. Queue/workflow jobs must revalidate tenant ownership and establish their own transaction-local context; do not trust serialized tenant IDs alone.

### Verify the deployed PostgreSQL role and policies

After deployment/migration, run:

```bash
python scripts/verify_postgres_rls.py
```

It checks all expected tables for enabled + forced RLS, the named policy, and rejects a current database role that is superuser or has `BYPASSRLS`. It does not prove the full application path, Cloudflare configuration, or cross-tenant behavior. A real PostgreSQL integration test using two tenants and the same pooled connection remains a release gate before multi-tenant activation.

## Prompt-injection controls

The reachable LLM surface found in this codebase is the optional customer-review cluster explanation. Imported CSV/review text can be attacker-authored. The path now:

- keeps computed counts and sentiment separate from customer-authored text;
- labels each review example as untrusted customer content with provenance;
- limits the model context to five examples of at most 1,500 characters each and a 10 KB serialized envelope;
- instructs the model to treat review content as data, not commands;
- exposes no tools or external actions in the chat-completion request;
- caps output to 350 tokens and 4,000 characters, accepts plain text only, and presents it as advisory;
- preserves deterministic counts/sentiment as the source of numeric truth.

This is layered risk reduction, not a perfect prompt-injection filter. A malicious review may still influence generated wording. The model output must never authorize a refund, change a payment state, select a tenant, or invoke a privileged tool. Refund/dispute actions continue to require deterministic server-side checks and merchant approval.

The MCP server currently exposes read-only PayPal context tools and deliberately omits refund/capture/write tools. PayPal responses and MCP tool outputs must still be treated as untrusted external data by any downstream agent.

## Regression tests added

- Hostile review instructions remain in the untrusted data envelope, not the system instruction.
- Review count and per-example context bounds are enforced.
- Non-text model output is rejected and output length is capped.
- RLS migration covers all 14 tenant-owned tables and uses both `USING` and `WITH CHECK`, plus `FORCE ROW LEVEL SECURITY`.
- Tenant context is set transaction-locally with a bound parameter.

## Remaining release gates

- Apply the migration to a disposable PostgreSQL instance and run two-tenant read/write isolation tests, including pooled connection reuse.
- Verify the actual Render/Cloudflare deployment role has neither superuser nor `BYPASSRLS`.
- If Cloudflare is adopted, inspect Worker auth, Hyperdrive transaction boundaries, caches, R2/KV, and queues in the deployed configuration.
- Migrate legacy SQLite business routes and storage before enabling multi-tenant mode.
- Review third-party LLM data-processing settings before sending merchant/customer review text to an external model provider.
- Perform browser screenshot/interaction QA at mobile, tablet and desktop sizes; build and browser runtime QA are separate from Python test results.
