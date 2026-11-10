# Deployment and integration status — v8.0 candidate

- Vercel: `frontend/vercel.json` provides SPA fallback. Configure project root as `frontend`, preset Vite, build `npm run build`, output `dist`, and `VITE_API_BASE` to the separately deployed API HTTPS origin. No Vercel project or deployment is created by this source package.
- FastAPI: deploy separately using the root `Dockerfile` or the Render Blueprint. Configure exact CORS origins, authentication and secrets in the host dashboard.
- PostgreSQL: provision separately and run `alembic upgrade head`; verify using the application DB role, not a superuser. Legacy business workflows are not fully migrated from SQLite.
- Render Workflows: configure service and shared secret in Render; exercise real delivery, retries and idempotency before claiming operational status.
- PayPal: Sandbox only. Configure credentials and webhook ID in backend secret storage. Verify signature validation and order/capture/refund/dispute flows with actual Sandbox events.
- Cloudflare Hyperdrive: optional architecture guidance only; not configured or operational in this package.
- Sponsor tools: AG Grid and Bryntum package dependencies are declared. APIMatic requires user-side activation. No sponsor integration is claimed operational without runtime evidence.

Do not expose a public API with demo auth settings, default secrets, or live payment execution enabled.
