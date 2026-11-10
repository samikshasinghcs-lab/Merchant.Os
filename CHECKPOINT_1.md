# MerchantOS — Checkpoint 1: Backend and Database

**Result: PASS for the current local MVP scope.**

## Work completed

- Fixed a syntax defect in the review text normalizer that prevented the backend from importing.
- Added `pytest.ini` so tests reliably import the application package.
- Added a FastAPI lifespan handler for database initialization, seed loading and initial review analysis (replacing deprecated startup event registration).
- Prevented repeated complaint-cluster analysis from creating duplicate active refund proposals for the same order. Rejected proposals may be proposed again; proposed/simulated/pending/completed proposals block duplicates.
- Added isolated API integration tests using temporary SQLite databases.

## Verification performed

- Python compilation: passed (`python -m compileall -q .`).
- Unit and API integration tests: **5 passed**.
- Live Uvicorn smoke test: `/health`, `/api/dashboard` and `/` returned HTTP 200.
- Seed validation: 15 illustrative orders, 40 reviews, 5 illustrative local dispute records (4 open; 1 under review).
- Demo refund workflow: proposal → approval → `SIMULATED`; repeat approval does not create a second action.
- Refund cap enforcement and rejection flow: passed.
- Dispute draft and audit endpoints: passed.

## Known limitations remaining

- The seeded PayPal order and capture identifiers are placeholders, not real PayPal Sandbox transactions.
- `DEMO_MODE=true` is the safe default and does not call PayPal.
- The SQLite refund flow is suitable for a single-process demo, not concurrent production use. A production implementation needs atomic reservation/locking around approvals and robust reconciliation for uncertain network outcomes.
- Authentication, merchant tenant isolation, verified PayPal webhooks, persistent evidence files and production-grade migrations are not implemented yet.
- Review classification is a transparent keyword baseline, not the final semantic embedding/LLM clustering engine.

## Run locally

```bash
pip install -r requirements.txt
python seed/generate_seed.py
uvicorn app.main:app --reload
```
