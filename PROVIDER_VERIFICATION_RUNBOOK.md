# Provider verification runbook (Sandbox only)

## Local and CI checks

Run `python scripts/provider_preflight.py` with the Render and PayPal Sandbox environment variables configured. This script only checks presence and safe mode; it does not call PayPal or Render and cannot claim live connectivity.

## PayPal Sandbox end-to-end

1. Set `PAYPAL_MODE=sandbox`; never set live credentials.
2. Set `DEMO_MODE=false` only in the isolated Sandbox test service.
3. Keep `PAYPAL_EXECUTION_ENABLED=false` until the test merchant has a dedicated disposable Sandbox capture and an independently approved refund request.
4. Create/capture the dedicated Sandbox order through the normal checkout flow.
5. Reconcile the provider capture, create a refund approval request, approve it with a different OWNER/ADMIN, then execute through the existing financial execution endpoint.
6. Verify PayPal's returned refund ID and status against the MerchantOS execution record and `/api/v1/financial-lifecycle/proof`.
7. Never use a production capture ID. Never retry an UNKNOWN provider outcome without reconciliation.

## Render Workflows end-to-end

1. Deploy the `merchantos-events` workflow service from `render.yaml`; its entrypoint is `python -m app.render_workflows`.
2. Configure `RENDER_API_KEY`, `WORKFLOW_SERVICE_SLUG`, `PUBLIC_APP_URL`, and a unique `MERCHANTOS_WORKFLOW_SHARED_SECRET` (32+ chars) in Render.
3. From an authenticated case detail, invoke `POST /api/v1/financial-lifecycle/cases/{case_id}/run-workflow`.
4. Confirm the returned run ID in Render's workflow run history and confirm the same run ID is stored in case events and `/proof`.
5. Confirm the workflow output has `financial_action: NONE`.

A live PayPal refund and live Render run require the merchant's own Sandbox account and deployed Render service. They cannot be truthfully verified in a source-only build environment without those credentials and resources.
