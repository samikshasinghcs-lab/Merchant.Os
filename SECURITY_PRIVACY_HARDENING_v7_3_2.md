# MerchantOS v7.3.2 — Security & Privacy Hardening Notes

## Changes in this checkpoint

- Hosted review embeddings and hosted LLM explanations are disabled unless
  `MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING=true` is explicitly configured.
  With the default setting, review text stays on the local processing path.
- Production readiness fails if hosted review processing is enabled without
  explicit `MERCHANTOS_EXTERNAL_REVIEW_DPA_ACK=true` and
  `MERCHANTOS_EXTERNAL_REVIEW_REDACTION_ACK=true` operator acknowledgements.
- Evidence files are written with restrictive directory/file permissions
  (0700/0600 where supported), exclusive file creation, and symlink checks.
- Image inspection rejects images above a 40-million-pixel limit; PDF inspection
  rejects documents above 500 pages and extracts text from at most 30 pages.
- Privacy export helpers require a 128-bit minimum pseudonymization key and
  always remove credential-like fields, even when a caller requests preservation.
- The experimental Gaussian privacy accountant rejects non-finite and negative
  spend parameters and validates release objects before accounting.
- Production readiness requires an absolute evidence-storage path outside the
  web-served static directory.

## Important limitations — not a compliance certification

- Evidence uploads are **not malware-scanned** in this release. Do not accept
  untrusted evidence uploads in a production environment until an antivirus or
  content-disarm pipeline is deployed and verified.
- Evidence storage is local filesystem storage, not tenant-scoped object storage.
  The existing legacy SQLite evidence workflow is single-merchant only.
- Tenant isolation is not complete across legacy routes, files, caches, or SQLite.
  Keep `MULTI_TENANT_ENABLED=false` and restrict the deployment to the documented
  single-merchant pilot.
- ConsentLedger remains an in-memory research prototype; it is not integrated as
  a durable consent-management or legal-basis system.
- The Gaussian mechanism is an experimental primitive. The accountant is in-memory
  and process-local; it does not provide durable, distributed privacy-budget
  enforcement. Correct DP claims require contribution bounding/clipping, a declared
  adjacency model, protected randomness, and end-to-end review of the release path.
- No MFA, refresh-token rotation/revocation, distributed rate limiting, independent
  penetration test, malware scan, or formal DP audit is claimed by this checkpoint.
- This work does not establish compliance with the DPDP Act, GDPR, PCI DSS, or any
  other legal or security standard. Obtain qualified legal and security review.

## Deployment settings

For a public deployment, set `APP_ENV=production`, `AUTH_REQUIRED=true`, a unique
random `JWT_SECRET_KEY` of at least 32 characters, `DEMO_MODE=false`,
`PAYPAL_MODE=sandbox`, `PAYPAL_EXECUTION_ENABLED=false`,
`MULTI_TENANT_ENABLED=false`, and a private persistent absolute
`EVIDENCE_UPLOAD_DIR` outside `app/static`. Follow every additional check reported
by `/ready`. Never commit `.env` files or credentials.
