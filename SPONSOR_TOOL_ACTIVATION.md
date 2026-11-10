# MerchantOS sponsor-tool activation

This change wires the four requested sponsor tools into the project source. Cloud account activation and package installation are separate operator steps; no credentials are committed.

## 1. APIMatic PayPal Context Plugin

The plugin is a coding-agent context integration, not a runtime dependency of MerchantOS. From the repository root on a development machine with Node.js 18+:

```bash
./scripts/activate-apimatic-paypal.sh
```

The underlying official install command is `npx --yes context-plugins install paypal`. Reload the coding assistant and confirm that the PayPal Context Plugin is listed/enabled. It provides API-spec and SDK context to the developer's coding agent; it does not become a deployed MerchantOS runtime service.

## 2. Render Workflows

A workflow service is declared in `render.yaml` as `merchantos-events`. Its entrypoint is `python -m app.render_workflows`; it registers `process_paypal_event`. The API verifies PayPal's webhook signature first, strips payer/contact/shipping details, and queues the event with an idempotency key. The workflow calls the internal callback using a 256-bit-or-stronger shared secret. This workflow records event metadata only; it cannot execute captures, refunds, invoice sends, or vault writes.

Configure the following secrets/values in Render for the API service and workflow service:

- `PUBLIC_APP_URL`: HTTPS URL of the MerchantOS API service (both services).
- `MERCHANTOS_WORKFLOW_SHARED_SECRET`: same random secret on both services, at least 32 characters.
- API service: `RENDER_API_KEY`, `WORKFLOW_SERVICE_SLUG=merchantos-events`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`.
- Configure the PayPal Sandbox webhook to deliver to `https://<api-host>/api/paypal/webhooks/receive` and subscribe to the event types required by the demo.

After deploy, verify a test webhook reaches `QUEUED` then `PROCESSED` in `GET /api/paypal/webhooks/events`. The task slug is `merchantos-events/process_paypal_event`. Render Workflows must be created/released in the connected Render workspace before dispatch can succeed.

Local validation (requires Render CLI 2.12+ and SDK installed):

```bash
render workflows dev -- python -m app.render_workflows
render workflows tasks list --local
```

## 3. AG Grid Community

The transaction ledger now uses `ag-grid-react` + `ag-grid-community` Community modules, backed by `GET /api/transactions`. It has filtering, sorting, pagination and no Enterprise-only feature dependency. Install via `cd frontend && npm install`.

## 4. Bryntum Scheduler Community

The execution timeline now uses `@bryntum/scheduler-react-community` and the Community Scheduler package. It maps persisted audit rows from `GET /api/audit` to read-only timeline markers; it does not fabricate agent thoughts or claim provider execution. Community is MIT-licensed and requires no license key.

The project includes `.mcp.json` registering AG Grid's `ag-mcp` stdio server and Bryntum's official remote documentation MCP endpoint for compatible coding agents. Restart the coding agent after opening the repository and verify both servers are enabled.

Install frontend dependencies with `cd frontend && npm install`, then run `npm run typecheck && npm run build`.

## Activation truth table

| Tool | Source wiring | External activation still needed |
|---|---|---|
| APIMatic | Activation script and exact PayPal Context Plugin install command | Run script in a supported IDE environment; reload and verify plugin enabled |
| AG Grid MCP | `.mcp.json` registers `npx ag-mcp` for version-aware grid documentation | Install dependencies on first launch if prompted; verify `ag-mcp` is enabled |
| Bryntum MCP | `.mcp.json` registers `https://mcp.bryntum.com` | Verify remote server enabled in compatible coding agent |
| Render Workflows | SDK dependency, workflow task, verified webhook dispatch, callback, Blueprint | Deploy/release workflow, set secrets, register PayPal Sandbox webhook |
| AG Grid | React Community ledger component and package pins | Install npm packages and run frontend build |
| Bryntum | Scheduler Community timeline, styles, package pins, MCP config | Install npm packages and run frontend build; enable MCP in compatible IDE |

## Safety and privacy

- No sponsor API keys or licenses are embedded in source.
- Webhook signature verification occurs before workflow dispatch.
- Workflow payload is allowlisted and excludes payer names, email addresses, shipping addresses and raw funding data.
- Workflow processing is idempotent by PayPal event ID.
- The Render task cannot perform financial writes.
- The UI exposes recorded audit events, not hidden chain-of-thought.
