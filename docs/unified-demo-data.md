# Unified tenant demo data

MerchantOS can seed a connected synthetic commerce story into one authenticated merchant
workspace. The seed is opt-in, idempotent, and tenant-scoped.

## Enable

Set this environment variable on the API service:

```text
MERCHANTOS_DEMO_SEED_ENABLED=true
```

Deploy the API, sign in as the workspace OWNER, and call:

```http
POST /api/v1/demo/seed
Authorization: Bearer <merchant access token>
```

The endpoint seeds only the authenticated owner's tenant. Repeating the request is safe:
existing deterministic demo rows are left unchanged and no duplicate rows are added.

## Read the connected dataset

- `GET /api/v1/demo/graph` — synthetic customer profiles, purchase histories, reviews,
  refund proposals, disputes, evidence placeholders, and financial cases joined by IDs.
- `GET /api/v1/demo/product-batches` — batch-level complaint signals computed from the
  synthetic order/review set.
- Existing tenant endpoints remain available:
  `/api/v1/domain/orders`, `/api/v1/domain/reviews`,
  `/api/v1/financial-lifecycle/overview`, `/api/v1/financial-lifecycle/cases`,
  and `/api/v1/financial-lifecycle/cases/{case_id}/events`.

## Seed contents

- 15 synthetic customer profiles with 30 linked orders (two purchases each).
- 30 reviews, each linked to an order and complaint cluster.
- 6 refund proposals, 3 illustrative dispute records, and 9 evidence placeholders.
- 6 financial resolution cases with 18 timeline events.
- 30 order-cost rows, 6 inspection instructions, and 3 product/batch insight rows.
- Tenant audit events documenting the synthetic seed.

## Safety boundaries

Every row is marked `SYNTHETIC_DEMO` or uses a `DEMO-` identifier. Demo orders use
`payment_status=DEMO_ONLY`, have no PayPal order/capture identifiers, and cannot be
mistaken for provider-confirmed payments. Refunds are proposals only. Dispute records
are explicitly not PayPal disputes. Evidence entries are placeholders with
`DEMO_NOT_VERIFIED` integrity status. Inventory dispositions are instructions only;
they do not change stock. No PayPal webhook events, provider transactions, refund
executions, or payment confirmations are generated.

The endpoint requires the authenticated workspace OWNER and an explicit deployment
feature flag. All reads and writes filter by the authenticated tenant ID. Demo records
are additive and are never used to overwrite existing merchant records.
