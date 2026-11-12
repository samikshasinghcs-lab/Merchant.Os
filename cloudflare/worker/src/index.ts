/**
 * Cloudflare Worker + Hyperdrive reference implementation.
 *
 * Verifies MerchantOS HS256 access tokens, checks current user/membership in
 * PostgreSQL, derives tenant_id from DB membership (not request input),
 * then establishes transaction-local RLS context.
 *
 * Set secrets with: wrangler secret put JWT_SECRET_KEY
 */
import { Client } from "pg";

interface Env {
  HYPERDRIVE: { connectionString: string };
  JWT_SECRET_KEY: string;
  JWT_ISSUER?: string;
  JWT_AUDIENCE?: string;
}

type Principal = {
  sub: string;
  tenant_id: string;
  exp: number;
  iss: string;
  aud: string;
};

function b64url(s: string) {
  return Uint8Array.from(
    atob(
      s.replace(/-/g, "+")
        .replace(/_/g, "/")
        .padEnd(Math.ceil(s.length / 4) * 4, "=")
    ),
    c => c.charCodeAt(0)
  );
}

async function verifyToken(
  request: Request,
  env: Env
): Promise<Principal> {
  const auth = request.headers.get("Authorization") || "";

  if (!auth.startsWith("Bearer ")) {
    throw new Error("AUTH_REQUIRED");
  }

  const parts = auth.slice(7).split(".");

  if (parts.length !== 3) {
    throw new Error("BAD_TOKEN");
  }

  const [h, p, s] = parts;

  const header = JSON.parse(
    new TextDecoder().decode(b64url(h))
  );

  if (header.alg !== "HS256") {
    throw new Error("BAD_ALGORITHM");
  }

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(env.JWT_SECRET_KEY),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"]
  );

  const signed = new TextEncoder().encode(`${h}.${p}`);

  if (
    !await crypto.subtle.verify(
      "HMAC",
      key,
      b64url(s),
      signed
    )
  ) {
    throw new Error("BAD_SIGNATURE");
  }

  const claims = JSON.parse(
    new TextDecoder().decode(b64url(p))
  );

  const now = Math.floor(Date.now() / 1000);

  if (
    !claims.sub ||
    !claims.exp ||
    claims.exp <= now ||
    claims.nbf > now ||
    claims.iss !== (env.JWT_ISSUER || "merchantos-api") ||
    claims.aud !== (env.JWT_AUDIENCE || "merchantos-client")
  ) {
    throw new Error("INVALID_CLAIMS");
  }

  return claims;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "private, no-store",
      "vary": "Authorization"
    }
  });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": new URL(request.url).origin,
          "access-control-allow-methods": "GET,OPTIONS",
          "access-control-allow-headers": "Authorization,Content-Type",
          "vary": "Origin"
        }
      });
    }

    if (request.method !== "GET") {
      return json({ error: "METHOD_NOT_ALLOWED" }, 405);
    }

    let principal: Principal;

    try {
      principal = await verifyToken(request, env);
    } catch (e: any) {
      return json({
        error: e.message === "AUTH_REQUIRED"
          ? "AUTH_REQUIRED"
          : "INVALID_TOKEN"
      }, 401);
    }

    const path = new URL(request.url).pathname;

    const client = new Client({
      connectionString: env.HYPERDRIVE.connectionString
    });

    try {
      await client.connect();
      await client.query("BEGIN");

      // Verify active identity and membership inside the same transaction.
      const member = await client.query(
        `SELECT m.tenant_id, m.role
         FROM users u
         JOIN memberships m ON m.user_id = u.id
         WHERE u.id = $1
           AND u.is_active = true
           AND m.tenant_id = $2
         LIMIT 1`,
        [principal.sub, principal.tenant_id]
      );

      if (!member.rowCount) {
        await client.query("ROLLBACK");
        return json({ error: "INACTIVE_MEMBERSHIP" }, 403);
      }

      const tenantId = member.rows[0].tenant_id as string;

      await client.query(
        "SELECT set_config('app.tenant_id', $1, true)",
        [tenantId]
      );

      let result;

      if (path === "/api/v1/financial-lifecycle/cases") {
        result = await client.query(
          `SELECT
             id,
             order_id,
             case_type,
             status,
             reason,
             complaint_cluster_id,
             requested_amount,
             estimated_loss,
             realized_loss,
             recoverable_inventory_estimate,
             recovered_inventory_actual,
             created_at,
             updated_at
           FROM financial_resolution_cases
           WHERE tenant_id = $1
           ORDER BY created_at DESC
           LIMIT 500`,
          [tenantId]
        );
      } else if (path === "/api/v1/financial-lifecycle/overview") {
        result = await client.query(
          `SELECT
             (SELECT count(*) FROM merchant_orders
              WHERE tenant_id = $1) AS order_count,
             (SELECT count(*) FROM financial_resolution_cases
              WHERE tenant_id = $1) AS case_count,
             (SELECT count(*) FROM financial_journal_entries
              WHERE tenant_id = $1) AS journal_entries`,
          [tenantId]
        );
      } else {
        await client.query("ROLLBACK");
        return json({ error: "NOT_FOUND" }, 404);
      }

      await client.query("COMMIT");

      return json({ items: result.rows });

    } catch (e) {
      try {
        await client.query("ROLLBACK");
      } catch {}

      return json({
        error: "DATABASE_REQUEST_FAILED"
      }, 500);

    } finally {
      await client.end().catch(() => {});
    }
  }
};
