# Cloudflare Worker + Hyperdrive deployment and PostgreSQL RLS

This bundle includes a Worker reference implementation at `cloudflare/worker/src/index.ts`.
It verifies the existing MerchantOS HS256 JWT, then rechecks active user and membership
inside the same PostgreSQL transaction. The tenant id is taken from the database
membership, not request input. It sets `app.tenant_id` transaction-locally and runs
tenant-filtered queries. Authenticated responses are `private, no-store`.

## Configure (operator actions required)
1. Provision Cloudflare Hyperdrive pointing at the existing PostgreSQL database.
2. Set the returned Hyperdrive config ID in `wrangler.toml`.
3. `wrangler secret put JWT_SECRET_KEY` and enter the same secret as Render's
   `JWT_SECRET_KEY` using the secure terminal prompt. Never commit the value.
4. Confirm the Hyperdrive origin role is a non-owner, non-superuser role with
   `rolsuper=false`, `rolbypassrls=false`; use a separate migration role.
5. `npx wrangler deploy`.
6. Add a Cloudflare route/custom domain only after verifying CORS, auth and origin TLS.
7. Test tenant A/B with separate accounts, including pool reuse A→B→A.

## Important limits
- This Worker exposes read-only `GET /api/v1/financial-lifecycle/overview` and `/cases`.
  It is a secure read-path reference, not a full replacement for the Render API.
- It does not receive PayPal webhooks or execute payment actions.
- It requires PostgreSQL tables and RLS migration to be applied first.
- It does not prove the live Cloudflare account, Hyperdrive binding or deployment exists.
- D1 does not support PostgreSQL RLS policies. For D1, every SQL operation must carry
  a server-derived tenant predicate such as `WHERE id=? AND tenant_id=?`.
