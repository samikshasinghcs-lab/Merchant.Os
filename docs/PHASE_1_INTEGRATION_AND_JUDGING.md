# MerchantOS Phase 1 — Integration & Judging Foundation

**Status:** code implementation started; external sponsor account activation and live Sandbox verification remain operator tasks.

## 1. PayPal integration map

| Product | API | MerchantOS implementation | Guardrail |
|---|---|---|---|
| Checkout | Orders v2 | Create order, buyer approval, capture | Sandbox-only; capture state recorded only on PayPal `COMPLETED` |
| Refunds | Payments v2 | Refund capture | Existing per-refund/daily caps, merchant approval, idempotency |
| Disputes | Disputes v1 | List/show, evidence submission | Sandbox-only; requested evidence, order match, file integrity and explicit confirmation |
| Invoices | Invoicing v2 | Create draft, retrieve, send | Sending requires explicit human approval phrase |
| Transaction intelligence | Transaction Search v1 | Search with RFC3339 range, status/currency/id filters | 31-day maximum; page bounds; documents up to 3-hour reporting lag |
| Vault | Payment Method Tokens v3 | PayPal Wallet setup token and approved setup-token finalization | Customer consent; payer approval checked with PayPal; no PAN/CVV accepted or stored |
| Webhooks | Webhook signature verification | Verify utility exists | Not yet a durable inbox/worker; do not trust or mutate state from a webhook until Phase 3 processing exists |

### Important scope notes
- The Vault flow is for a PayPal Wallet payment source. It intentionally does not accept raw card PAN or CVV.
- The application returns the payment token identifier to the caller but does not persist the token or payment-source object. Production use needs tenant-scoped token references, lifecycle controls, authorization scopes and compliance review.
- PayPal API access depends on the Sandbox app having the corresponding product permissions/scopes enabled. A route being present does not prove the remote API is enabled for a particular app.
- Transaction Search is a reporting surface, not a real-time event stream. PayPal documents that executed transactions may take up to three hours to appear.
- Invoice draft creation is not payer notification. Sending is a separate, approval-gated operation.

## 2. Sponsor integration plan (truthful status)

| Sponsor | Planned MerchantOS role | Current status | Acceptance evidence before claiming integration |
|---|---|---|---|
| APIMatic | Context Plugin to ground PayPal API implementation in official schemas | PayPal Context Plugin activation script added; actual IDE installation still requires running it in a supported developer environment | Plugin appears enabled in the coding agent; record schema-grounded endpoint implementation and contract tests |
| Render | Durable verified-webhook processing | Render SDK task, webhook signature verification → sanitized payload → idempotent task dispatch → shared-secret callback, plus workflow Blueprint added | Workflow service released in Render; Sandbox webhook reaches `PROCESSED`; retry and duplicate-delivery evidence |
| Postman | API collection and repeatable Sandbox verification | Collection added under `integrations/postman/` | Collection run export with passing requests against configured Sandbox |
| AG Grid | Financial transaction ledger | Community React grid wired to `GET /api/transactions` with filtering, sorting and pagination; npm install/build pending | Frontend build passes; live API rows rendered and filters/pagination demonstrated |
| Execution timeline | Operational audit timeline | Native React read-only timeline wired to persisted `/api/audit` records; no private scheduler package required | Frontend production build passes and real audit events are displayed |
| Channel3 | Not core to complaint/refund intelligence; potential product catalog enrichment only if MerchantOS adds merchant-side catalog matching | Deliberately not integrated | Only add if a real catalog workflow is implemented and Channel3 API/MCP is actually called |
| Elastic | Search over audit and operational events | Candidate for later observability phase | Indexed events, hybrid search and reproducible query demonstration |
| Zapier | Optional notifications/approval handoff | Candidate only | Authenticated MCP workflow and end-to-end approval evidence |
| Kernel / Astropods | Agent browser/agent runtime | Not selected for current core problem | A clear user outcome and safe, bounded integration before adoption |

No sponsor tool is represented as integrated merely because it appears in this plan. Sponsor components are optional in the hackathon rules; PayPal and AI are the core requirement.

## 3. APIMatic Context Plugin setup

1. Activate the PayPal AI Hackathon Context Plugin through the APIMatic sponsor access path.
2. Enable the PayPal context pack in the developer environment used for future PayPal API work.
3. Use it to verify request/response schema, OAuth scopes, idempotency headers and endpoint versions before implementing new calls.
4. Record which endpoint schema was consulted in the relevant implementation note or pull request.
5. Run Postman and pytest contract tests after each API change.

The plugin is an external developer-tool integration. This repository does not claim it is running inside the deployed MerchantOS server.

## 4. Local MCP server

A read-only MCP server is provided in `app/mcp_server.py`.

Run after installing requirements and configuring Sandbox credentials:

```bash
DEMO_MODE=false PAYPAL_MODE=sandbox python -m app.mcp_server
```

It exposes:
- `paypal_api_catalog`
- `search_paypal_transactions`
- `get_paypal_invoice`
- `get_paypal_dispute`

The MCP surface deliberately has no refund, capture, invoice-send, dispute-evidence-submit or vault-write tool. Agent access is read-only at this phase; all financial writes remain behind MerchantOS API authorization and human approval. Use a private MCP transport/host and explicit client allowlisting before exposing it outside a local developer process.

## 5. Balanced judging criteria — evidence plan

The official Devpost judging criteria are five equally weighted categories. This is the evidence we need, not a predicted score.

| Criterion | Product claim | Evidence to capture |
|---|---|---|
| Technological Implementation | Multiple PayPal APIs are central to the product; AI-assisted interpretation is bounded by deterministic operations | PayPal Sandbox order/capture/refund flow, invoice lifecycle, transaction search, vault approval, tests, API collection, architecture |
| Design | Coherent merchant investigation-to-resolution experience | Existing landing/workspace; later real-data dashboard and accessible execution timeline; responsive/browser test evidence |
| Potential Impact | Small merchants can connect complaints to paid orders, act on disputes and understand recurring product/batch issues | Reproducible seeded scenario, workflow timings measured in demo, clear merchant persona and limitations |
| Innovation / Idea | Complaint-to-financial-resolution intelligence rather than a generic payment chatbot | End-to-end evidence graph: feedback → order → capture → policy → approval → provider action → audit/root cause |
| Presentation | Judges can see a real, understandable outcome in under three minutes | Screen recording of real Sandbox event/action, PayPal response and MerchantOS audit trail; no mock-as-live visuals |

## 6. Phase 1 acceptance checklist

- [x] PayPal Orders/Payments/Disputes baseline retained.
- [x] Invoicing v2 draft/show/send adapter and API routes added.
- [x] Invoice send is human-confirmation gated.
- [x] Transaction Search v1 adapter and bounded query API added.
- [x] Vault v3 PayPal Wallet setup/finalize flow added without raw card collection.
- [x] Local read-only MCP server and tool catalogue added.
- [x] Postman collection added.
- [x] Sponsor tool status is explicitly distinguished from planned integrations.
- [x] Five equally weighted judging criteria mapped to evidence.
- [ ] APIMatic Context Plugin installed and enabled in the developer's supported coding agent; a concrete schema-grounded change recorded.
- [x] Render Workflows task and dispatch wiring added; external workflow release, secrets and PayPal webhook registration remain operator steps.
- [x] AG Grid Community wired into the transaction ledger; frontend package install and build remain pending.
- [x] Native React read-only audit timeline wired to persisted audit events; frontend production build remains a CI verification gate.
- [ ] PayPal Sandbox app scopes enabled and new Invoicing / Transaction Search / Vault flows verified with real credentials.

## Official references
- PayPal AI Hackathon and partner list: https://developer.paypal.com/community/blog/PayPal_AI_Hackathon/
- Hackathon judging criteria and submission requirements: https://paypalaihackathon.devpost.com/
- PayPal Invoicing v2: https://developer.paypal.com/api/invoicing/v2/
- PayPal Transaction Search v1: https://developer.paypal.com/api/transaction-search/v1
- PayPal Payment Method Tokens v3: https://developer.paypal.com/api/payment-tokens/v3/

### Sandbox configuration

```dotenv
DEMO_MODE=false
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_secret
PUBLIC_APP_URL=https://your-sandbox-demo.example
```

Enable the relevant Invoicing, Transaction Search and Vault products/permissions on the PayPal Sandbox app. If PayPal returns an authorization/scope error, treat that as an app-permission configuration issue; do not bypass the permission check or silently fall back to simulated success.


## Sponsor activation implementation update

See `docs/SPONSOR_TOOL_ACTIVATION.md` for the current source wiring, exact activation commands, deployment secrets, local validation steps and the distinction between code integration and external account activation.
