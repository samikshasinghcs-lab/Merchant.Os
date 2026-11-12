# MerchantOS competition demo runbook

## Before recording

1. Deploy the backend and frontend using the configured competition environment.
2. Keep `PAYPAL_MODE=sandbox`; never use live PayPal credentials.
3. Keep `DEMO_MODE=true` for static demo mode. If demonstrating a Sandbox refund, follow the separate approval path and only enable the documented Sandbox execution acknowledgement after confirming the environment is Sandbox.
4. Confirm persistent private evidence storage is mounted at `/var/data/merchantos-evidence` (or the configured private path).
5. Wake the Render free-tier service before the presentation. Open Render Logs in a separate tab.
6. Sign in and open `/financial-operations`; verify the top status strip and `/proof` page do not show fabricated IDs or uptime.

## Demo sequence

1. Open the cases grid. Explain the summary cards, filters, quick search, CSV export and case selection.
2. Select or create a case. Show customer/order context and the complaint message.
3. Explain the computed recommendation as a transparent heuristic, not a measured AI probability.
4. Run the deterministic policy assessment. If a rule fails, demonstrate that override requires a reason and is audited.
5. Upload one valid JPEG/PNG/PDF. Show the SHA-256 integrity result and evidence preview. Explain duplicate and file-size controls.
6. Show the disposition and financial preview: COGS, recovery, refund, return shipping, handling, payment-fee input and write-off. State that fee treatment is merchant-configured and must match the PayPal agreement.
7. Record a human decision with a reason and note. Explain that this does not itself move money.
8. For the optional payment segment, use the existing PayPal Sandbox workflow: reconcile capture, obtain an independent approver, execute with idempotency, and show provider-confirmed refund ID/status. Never bypass this path.
9. Run the Render resolution workflow if configured. Show its returned run ID and logs.
10. Open `/proof` and show the latest provider result, workflow reference, audit events and Sandbox/demo disclosures.

## Safe claims to make

- “AI/computed logic supports the investigation; deterministic policy checks and human approval control outcomes.”
- “The statistical output shows association, not proven causation.”
- “Sandbox payment actions only; no real money is moved during the demonstration.”
- “Implemented, Verified and Live are separate statuses; we only claim Live when the deployed provider confirms it.”

Never show credentials, access tokens, private evidence files, customer PII or environment-variable values on screen.
