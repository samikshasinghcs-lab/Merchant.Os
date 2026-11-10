# MerchantOS v7.3.2 — Security & Privacy Assurance Notes

## Scope and claim boundary

This document records implemented controls and known limitations for the current
hackathon/development checkpoint. It is not a penetration-test report, legal
opinion, DPDP certification, SOC 2 report, or production-readiness certificate.
The legacy merchant-domain data path still uses SQLite and is not suitable for
unrestricted multi-tenant deployment.

## Implemented controls observed in this codebase

| Area | Current implementation | Boundary / limitation |
|---|---|---|
| Authentication | JWT access tokens with issuer, audience, expiry, `jti`, active-user and membership checks | No complete refresh-token rotation or server-side `jti` revocation store |
| Passwords | bcrypt hashing and minimum password length checks | No MFA implementation; credential-stuffing protection is process-local |
| Authorization | Workspace roles and elevated-role checks for sensitive routes | Legacy SQLite records are not uniformly tenant-scoped |
| Tenant safety | PostgreSQL RLS migration and a fail-closed legacy-route guard when multi-tenant mode is enabled | PostgreSQL RLS must be tested against a real PostgreSQL deployment; do not enable multi-tenant mode before migration and integration tests |
| PayPal webhooks | Provider signature verification, event sanitization, idempotent event inbox, shared-secret workflow callbacks | Provider configuration and deployment secrets must be correctly provisioned |
| Financial execution | Approval controls, idempotency reservations, explicit execution states, and live execution disabled in this checkpoint | Not a production payment certification; provider reconciliation remains a separate operational requirement |
| Evidence uploads | Extension and magic-byte checks, size cap, structural inspection, generated storage names, SHA-256 integrity record, restrictive directory/file modes | No malware-scanning service; hashes establish byte integrity, not truth/authenticity; legacy evidence records are not fully tenant-isolated |
| Secrets | Fernet-encrypted credential support and production readiness checks for encryption key | Key rotation and managed KMS integration are not implemented |
| Privacy-aware analytics | Keyed pseudonymization and field minimization helpers; external review processing disabled by default and gated by explicit acknowledgements | Free text may contain identifiers; pseudonymization is not anonymization; privacy helper is not automatically applied to every data path |
| Differential privacy research | Gaussian mechanism calibration and basic composition helper | Experimental/in-memory only; not a complete DP system, durable privacy accountant, or release approval workflow |
| Audit | Hash-chain research implementation and operational audit records | A hash chain is tamper-evident only if checkpoints/keys are independently protected; not a substitute for immutable external storage |

## v7.3.2 hardening change

Production readiness now rejects evidence storage when the configured path:

- is the web-served `app/static` directory itself;
- is nested anywhere inside `app/static`;
- is configured as a symbolic link; or
- already exists with group/world permissions.

The evidence writer also applies restrictive `0700` directory and `0600` file
permissions when creating evidence storage and files. This is defense in depth;
operators must still use private persistent storage and verify the deployed
filesystem's behavior.

## Required deployment posture

1. Keep `PAYPAL_MODE=sandbox` and `PAYPAL_EXECUTION_ENABLED=false` for this checkpoint.
2. Set `APP_ENV=production`, `AUTH_REQUIRED=true`, and a unique high-entropy `JWT_SECRET_KEY` before any public deployment.
3. Use a valid, separately managed Fernet key for `MERCHANTOS_CREDENTIALS_KEY`; do not commit secrets to Git.
4. Keep `MULTI_TENANT_ENABLED=false` until all business repositories are tenant-scoped and PostgreSQL RLS has passed integration tests against PostgreSQL.
5. Set `EVIDENCE_UPLOAD_DIR` to a private persistent path outside all web-served directories. Restrict filesystem permissions and backups.
6. Keep external review/LLM processing disabled unless a documented processor, data minimization, contractual, and legal review has been completed.
7. Do not put real customer data, payment credentials, access tokens, or production database dumps in the repository or demo fixtures.
8. Review dependency and static-analysis workflow findings before release; resolve or explicitly document accepted risks.

## Privacy engineering requirements still open

- Map personal-data categories, purposes, lawful bases, recipients, and retention periods.
- Integrate consent/notice and preference handling into actual collection and processing flows where applicable; a prototype ledger alone is insufficient.
- Implement and test access, correction, deletion, and retention workflows across databases, evidence files, logs, exports, and backups.
- Add malware scanning and controlled evidence download authorization.
- Apply redaction/minimization before any external processor receives user-generated text.
- Establish durable privacy-budget accounting before releasing differentially private aggregates.
- Complete a jurisdiction-specific DPDP Act assessment with qualified counsel; technical controls alone do not establish legal compliance.

## Verification performed for this checkpoint

The test suite is run locally against the extracted project. GitHub Actions also
contains a dedicated security-audit workflow for dependency vulnerability and
Bandit static analysis. The GitHub workflow must complete successfully on the
actual repository before the merge is considered verified.
