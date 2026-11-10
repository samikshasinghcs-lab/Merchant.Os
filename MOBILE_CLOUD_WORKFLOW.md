# Mobile-first GitHub workflow

This repository can be managed from GitHub in a mobile browser. No local laptop is required for the CI checks.

1. Create a private GitHub repository and upload the contents of this source package (the `merchantos/` directory contents, not the ZIP itself).
2. Ensure the default branch is `main`.
3. Open **Actions → MerchantOS CI**. The workflow runs backend tests and the frontend TypeScript/Vite build on pushes and pull requests.
4. Resolve any failed check before merging. Do not bypass a red security or build check.
5. Store deployment credentials only in GitHub/Vercel/hosting environment secret stores. Never upload `.env`, database files, tokens or provider secrets.
6. Use Vercel with the project Root Directory set to `frontend`, framework preset `Vite`, and build command `npm run build`. The SPA rewrite is in `frontend/vercel.json`.
7. Set `VITE_API_BASE` to the HTTPS URL of the separately hosted FastAPI service. Configure backend CORS to allow the exact Vercel production and preview origins you intend to use.
8. Deploy the API and PostgreSQL separately. Vercel hosting the static frontend does not host the Python API or durable workflow worker.

The CI workflow currently uses `npm install` because the source package did not contain a package lock and dependency-lock generation could not be completed in this environment. Commit the generated `frontend/package-lock.json` from a successful CI/developer install and change the workflow to `npm ci` in a later reproducibility pass.
