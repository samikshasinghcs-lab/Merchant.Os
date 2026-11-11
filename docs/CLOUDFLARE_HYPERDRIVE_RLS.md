# MerchantOS PostgreSQL RLS + Cloudflare Hyperdrive

## What is already in this repository

MerchantOS already has a PostgreSQL RLS migration at `alembic/versions/20261110_01_tenant_rls.py`. It enables and forces RLS on the declared tenant-owned tables and creates policies with both `USING` and `WITH CHECK` predicates against `app.tenant_id`. `app/tenant_db.py` derives the context from a server-verified tenant ID and executes `set_config('app.tenant_id', ..., true)` inside the SQLAlchemy session transaction.

The `true` argument makes the setting transaction-local. `tenant_api.py` gets the tenant from `identity.current_principal`, never from a request body. Keep `MULTI_TENANT_ENABLED=false` until every legacy SQLite route and file/cache store has been migrated; the existing `SECURITY.md` correctly records that the overall application is still a single-merchant pilot.

## Hyperdrive requirements

Cloudflare Hyperdrive uses transaction pooling. A connection is pinned to a transaction, then returned to the pool when that transaction ends. Do not use session-level `SET app.tenant_id`, do not assume a connection remains assigned to a Worker invocation, and do not issue the tenant context and protected query as unrelated autocommit statements.

For a Cloudflare Worker that directly accesses this PostgreSQL database, use one explicit transaction and parameterized SQL. Derive `tenantId` only after validating the caller's signed identity and active membership on the server. Never accept `tenant_id` from JSON, query parameters, headers, model output, or a URL as authorization evidence.

Illustrative TypeScript pattern (not a deployed Worker):

```ts
import { Client } from "pg";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const principal = await verifyMerchantOSAccessToken(request, env.JWT_SECRET);
    // `verifyMerchantOSAccessToken` must validate signature, issuer, audience,
    // expiry, subject, and active membership against the trusted identity store.
    const tenantId = principal.tenant_id;

    const client = new Client({ connectionString: env.HYPERDRIVE.connectionString });
    await client.connect();
    try {
      await client.query("BEGIN");
      await client.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);
      const result = await client.query(
        "SELECT id, product, amount, payment_status FROM merchant_orders ORDER BY created_at DESC LIMIT 100"
      );
      await client.query("COMMIT");
      return Response.json(result.rows);
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    }
    // Hyperdrive manages the underlying origin pool. Create the client per request.
  }
};
```

`verifyMerchantOSAccessToken` above is intentionally an integration seam, not a stub that should be deployed as-is. Use the same trusted identity and membership verification as the API. A signature-valid JWT alone does not prove the membership remains active.

## Database role requirements

- The Hyperdrive/API runtime role must not be a PostgreSQL superuser and must not have `BYPASSRLS`.
- The application role should not own tenant tables where avoidable. `FORCE ROW LEVEL SECURITY` is already applied, but superusers and `BYPASSRLS` roles still bypass policies.
- Keep migrations on a separate privileged deployment role; do not give that role to the Worker or API runtime.
- Ensure all tenant-owned reads, writes, list/search/aggregate/export paths use tenant context and tenant predicates. RLS is defense in depth, not a replacement for application authorization.
- Do not share personalized responses through a cache key that omits the authenticated tenant. Prefer bypassing shared cache for authenticated tenant data.
- For queues, scheduled tasks and workflows, persist and validate tenant context on job creation and execution; do not trust a payload tenant ID by itself.

## Verification checklist

1. Apply the existing migration to a disposable PostgreSQL database.
2. Connect using the actual non-owner, non-superuser runtime role.
3. Confirm `rolsuper=false` and `rolbypassrls=false` for that role.
4. Seed two tenants and verify tenant A cannot SELECT, UPDATE or DELETE tenant B rows; verify INSERT/UPDATE with a foreign tenant ID fails.
5. Verify missing `app.tenant_id` returns zero rows and rejects writes.
6. Reuse pooled connections in alternating A/B/A transactions and verify no tenant context leaks.
7. Repeat through the actual Hyperdrive binding if a Worker is introduced.
8. Verify every route and asynchronous path, not only the `/api/v1/domain` examples.

## Scope boundary

This patch does not create or deploy a Cloudflare Worker, Hyperdrive binding, Access policy, database migration, or Cloudflare account configuration. The repository's existing RLS migration and tenant session helper are the implementation foundation; this guide defines the safe Hyperdrive transaction contract. A deployed Cloudflare path remains unverified.
