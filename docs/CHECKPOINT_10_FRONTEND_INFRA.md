# Checkpoint 10 — Frontend & Infrastructure Foundation

## Verification
- Existing backend suite: **23 passed**.
- Python compilation: passed.
- TypeScript/TSX transpile syntax checks: passed.
- Full npm dependency install and Vite production build: **not verified** (npm install timed out because package registry networking was unavailable in the build environment).
- Docker image/Compose startup and Alembic against PostgreSQL: **not verified** (Docker is unavailable in this environment).

## Delivered
- React + TypeScript + Vite frontend with responsive MerchantOS shell and route navigation.
- Dedicated pages for command center, customer investigation, review lab/import, transaction investigation, refund queue, dispute center, evidence vault, agreement workspace, milestone workspace and audit history.
- Shared typed API helper with bearer token injection, error handling and currency formatting.
- SQLAlchemy 2 identity models for users, tenants and memberships.
- Password hashing, JWT login/register/me endpoints and workspace membership/role endpoints.
- Alembic migration for identity schema.
- Coarse role enforcement when `AUTH_REQUIRED=true`.
- Dockerfiles, Docker Compose (PostgreSQL + API + Nginx frontend), Render blueprint and reverse-proxy config.

## Important incomplete areas
- Core business-domain tables still use SQLite; PostgreSQL currently backs identity/workspace records only.
- No tenant_id on orders/reviews/refunds/disputes/evidence/agreements/milestones/audit. Multi-tenant registration is deliberately restricted to one workspace with HTTP 409 for any second workspace. Do not describe this as multi-merchant isolation.
- RBAC is coarse-grained, not a full permissions matrix. Role assignment and invitation workflows require hardening.
- No production deployment has been performed. Render blueprint and Docker config are deployment scaffolding.
- Frontend package installation/build could not be verified in this environment because npm dependency installation timed out with network unavailable.
- The legacy dashboard is still served by FastAPI at `/`; the new React app is served by the frontend container at port 8080 in Compose.

## Local frontend
```bash
cd frontend
npm install
npm run dev
```
Vite runs on port 5173. Set `VITE_API_BASE=http://localhost:8000` in `frontend/.env.local` for local development.

## Docker
```bash
cp .env.example .env
# Set POSTGRES_PASSWORD and JWT_SECRET_KEY to strong unique values.
docker compose up --build
```
Open `http://localhost:8080`. API is exposed on `http://localhost:8000`.

## Identity endpoints
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/v1/workspace`
- `GET /api/v1/workspace/members`
- `POST /api/v1/workspace/members/{user_id}/role`

Production Docker sets `AUTH_REQUIRED=true`. The first workspace registration is allowed; further workspace registration is blocked until domain-level tenant isolation is implemented.
