# Checkpoint 8 — Evidence Vault & PayPal Dispute Intelligence

## Implemented

### Evidence files
- `POST /api/evidence/upload?order_id=...&evidence_type=...&description=...` accepts PDF, PNG, JPG/JPEG, GIF, TXT and CSV uploads.
- Files are stored under `EVIDENCE_UPLOAD_DIR` using generated IDs; the original filename is sanitized and never used as the storage path.
- Upload size is bounded by `MAX_EVIDENCE_FILE_BYTES` (default 10 MiB; the implementation rejects files at or above this limit).
- File signatures are checked against extensions. PDF and image structures are inspected using `pypdf` and Pillow. PDF text extraction and image metadata are recorded when available.
- A SHA-256 hash is stored at ingestion. `POST /api/evidence/files/{file_id}/verify-integrity` recomputes the hash and reports whether the stored bytes have changed.
- `GET /api/evidence/files` lists metadata; `GET /api/evidence/files/{file_id}/inspect` returns inspection and integrity information.

**Authenticity limitation:** a hash match proves only that the stored bytes match the bytes originally registered. It does not prove authorship, when the file was created, whether metadata is genuine, or whether the claims in it are true. Merchant-provided provenance is not independently authenticated. No cryptographic signer/issuer validation or forensic authenticity service is implemented.

### PayPal Disputes API
- `POST /api/paypal/disputes/sync` lists disputes from the configured PayPal Sandbox account and retrieves details for each dispute.
- `GET /api/paypal/disputes` returns synchronized disputes with deadline-state labels; `GET /api/paypal/disputes/{dispute_id}` returns the stored provider payload.
- Seller response due dates are stored and classified as overdue, due within 24 hours, due within 3 days, upcoming, or unknown.
- `POST /api/paypal/disputes/{dispute_id}/submit-evidence` supports PayPal's multipart `provide-evidence` operation.
- Submission is blocked unless the operator supplies `human_approved=true` and the exact confirmation phrase `SUBMIT TO PAYPAL`, the provider dispute status is `WAITING_FOR_SELLER_RESPONSE`, the evidence type is requested by PayPal when requested evidence is listed, the evidence package passes file integrity/type/size checks, and the merchant explicitly links the files to a local order.
- A repeated identical package is blocked while submitting or after submission.
- Submission attempts, approvals, provider responses and failures are audit logged.

PayPal evidence submission accepts PDF, JPG/JPEG, GIF and PNG files, each smaller than 10 MB, with a maximum aggregate request size of 50 MB. The application enforces these limits. PayPal may require evidence-specific `evidence_info` fields (such as tracking information or refund IDs); this version submits file documents and notes only, so those specialized payloads remain a follow-up enhancement.

## Important safety and deployment limitations

- All PayPal dispute API operations are restricted to Sandbox and require `DEMO_MODE=false`, `PAYPAL_MODE=sandbox`, and Sandbox REST credentials.
- No live PayPal dispute has been fetched or submitted in the automated test run. Tests mock the provider adapter; an actual Sandbox dispute must be created using PayPal's documented dispute simulation/test flow and then verified manually.
- The explicit approval phrase is a workflow safeguard, not authentication. The current app has no login or merchant identity system. Do not expose submission endpoints to the public internet until authentication, authorization, tenant isolation, CSRF protections, rate limits, encrypted storage, and operational controls are implemented.
- Uploaded files are stored locally. Production requires private object storage, malware scanning, retention/deletion policy, access controls and encrypted-at-rest storage.
- Inspection extracts text/metadata; it does not judge factual truth or establish authenticity. Image OCR and semantic visual inspection are not included.
- PayPal dispute status and deadline data are only as fresh as the last successful sync. Add scheduled synchronization and verified PayPal webhooks before production.

## Environment

```env
DEMO_MODE=true
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
EVIDENCE_UPLOAD_DIR=evidence_uploads
MAX_EVIDENCE_FILE_BYTES=10485760
```

To enable Sandbox dispute API calls, set `DEMO_MODE=false` and configure the Sandbox credentials. Keep secrets server-side.

## Verification

Automated suite: **22 passed**. Coverage includes upload validation, text extraction, SHA-256 match/mismatch detection, PayPal-specific file type restrictions, explicit human approval, order-linked evidence checks, duplicate submission blocking, mocked provider submission and dispute sync/deadline classification. The PayPal HTTP operations are mocked in tests; this is not a claim that a live Sandbox dispute was retrieved or submitted.
