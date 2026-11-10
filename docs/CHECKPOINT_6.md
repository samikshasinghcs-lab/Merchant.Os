# MerchantOS v0.6 — Checkpoint 6

## Trust, Accountability & Intelligence Command Centre

### Delivered
- `GET /api/accountability` provides separately observable operational indicators.
- Resolution counts by lifecycle status.
- Open and total dispute counts.
- Registered evidence count and distinct orders with evidence.
- Payment status counts.
- Refund counts and values grouped by **currency and status** (never summed across currencies).
- Ten most recent audit events.
- Explicit methodology and limitations in the API response.
- Dashboard panel surfaces core accountability indicators.

### Trust and safety design
- No opaque composite trust score is generated.
- Evidence registration is not authentication: merchant-supplied evidence remains unverified.
- Correlation is not presented as causation.
- Refund totals remain separated by currency and status.
- Existing human-approval requirements for financial actions remain unchanged.

### Verification performed
- Automated test suite: 16 passed.
- Python compilation: passed.
- FastAPI TestClient smoke checks: `/`, `/health`, `/api/dashboard`, and `/api/accountability` returned HTTP 200.

### Not production-ready
This remains a hackathon MVP. Authentication, tenant isolation, robust authorization, production-grade migrations, webhook verification, concurrency-safe financial reservations, monitoring, and independent security review are still required before handling real merchants or money.
