# MerchantOS v6.3 — Security hardening record

## Changes applied

1. **First-owner bootstrap is closed by default.** Public registration now requires an operator-provisioned `MERCHANTOS_BOOTSTRAP_REGISTRATION_TOKEN` of at least 32 characters, supplied in `X-MerchantOS-Bootstrap-Token`. Existing single-tenant registration lock remains in place. Keep this value out of source control and rotate/remove it after initial provisioning.
2. **JWT access tokens are more tightly scoped.** Tokens now include issuer, audience, `nbf`, `jti`, and a short bounded lifetime (5–60 minutes; default 15). Decode paths require those claims and validate issuer/audience. Role is deliberately not trusted from token claims; current membership role is read from the identity database on each authenticated request.
3. **Sensitive operation checks expanded.** Financial approvals, captures, authorizations, dispute evidence submission, vault, refund-approval and PayPal credential routes require OWNER/ADMIN. Role changes are OWNER-only. The existing operator/viewer write restrictions remain.
4. **Authentication endpoint throttling added.** Login and bootstrap-registration attempts are limited to 8 per source IP per 60 seconds per process. This is a local fallback only; production needs a shared Redis/API-gateway rate limiter to cover multiple workers and instances.
5. **HTTP hardening headers added.** Responses now include `nosniff`, frame denial, strict referrer policy, restrictive permissions policy, same-origin resource policy, and no-store caching for API responses. HSTS is emitted when the application sees HTTPS.
6. **Request body size guard added.** Requests with declared oversized Content-Length are rejected early; upload handlers still apply file-type and file-size validation.

## Security boundaries that remain

- Legacy merchant business data still lives in a shared SQLite database without tenant_id-scoped access. The deployment must remain single-merchant; do not advertise multi-tenant SaaS isolation.
- The process-local rate limiter is not distributed and does not replace gateway/WAF controls.
- No MFA, refresh-token rotation/revocation, verified email, account recovery, or session/device management is implemented.
- No malware scanning or content-disarm pipeline is present for evidence uploads. Store uploads privately and do not serve them directly from a public static path.
- JWT revocation is not immediate; disable the user/membership and use short token lifetime. Add a server-side token/session version or denylist before broader production use.
- Webhook routes depend on PayPal's signature verification. Internal workflow callbacks depend on the shared HMAC secret. Keep both credentials separate, high entropy, and rotated.
- HSTS only works when TLS terminates correctly and the trusted proxy preserves the HTTPS scheme. Configure HTTPS and trusted proxy behavior at the edge.
- Content-Length checks do not protect against all chunked/streamed body abuse; enforce request limits at the reverse proxy/API gateway too.

## Required before public production

1. Complete tenant isolation for every business table, query, background task, evidence object, credential, and audit record; add cross-tenant denial tests.
2. Add distributed rate limiting, WAF/bot protection, request timeouts, connection limits, and trusted-host allowlisting at the edge.
3. Add MFA for financial approvals, verified email, secure account recovery, token revocation/rotation, and explicit endpoint permission dependencies.
4. Add malware scanning and private object storage for evidence, plus backup/restore and incident-response drills.
5. Run dependency, SAST, DAST, secret-scanning, and penetration tests; review production configuration and key rotation.
6. Perform a full browser/API integration test and a PayPal Sandbox end-to-end verification. These changes do not establish production readiness.

## Verification

Security hardening tests cover JWT issuer/audience binding and current-database role sourcing. Full backend test suite result is recorded in the release handoff, not inferred from this document.
