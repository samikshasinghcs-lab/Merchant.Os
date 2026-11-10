# MerchantOS v0.7 — Merchant Intelligence expansion

## Implemented
- CSV review ingestion (5 MB limit), flexible common-column mapping, UTF-8/Latin-1 decoding, generated IDs where missing, duplicate-safe imports and import history.
- Import adapters for generic, Shopify-export, Trustpilot-export and Google-reviews-export CSV formats. These ingest merchant-authorized exports; live OAuth/API connectors are not enabled.
- Review analysis with sentence-transformers embeddings when installed; hosted OpenAI-compatible embeddings when `OPENAI_API_KEY` is configured; TF-IDF cosine fallback otherwise. Connected-component clustering is deterministic for a given vector model and threshold.
- Sentiment analysis with VADER when installed and a transparent lexicon fallback otherwise. Rating contributes as a secondary signal.
- Cluster explanations use an optional OpenAI-compatible chat-completions endpoint. Without credentials, a deterministic computed summary is returned and explicitly labelled as not LLM-generated.
- Customer investigation endpoint and UI: `/api/customers`, `/api/customers/{customer_id}`.
- Transaction investigation endpoint and UI: `/api/transactions/{order_id}`; accepts local order ID, PayPal order ID or capture ID.
- Match candidate endpoint and manual association endpoint. HIGH = exact order reference (and customer reference where present); MEDIUM = exact customer reference only; no association is created for unrelated records. Merchant confirmation is recorded.
- Review Lab and investigation sections added to the existing dashboard.

## Configuration
- `MERCHANTOS_SIMILARITY_THRESHOLD` (default `0.28`)
- `MERCHANTOS_EMBEDDING_MODEL` (default `sentence-transformers/all-MiniLM-L6-v2`; install `sentence-transformers` to use locally)
- `OPENAI_API_KEY` (optional; enables hosted embeddings and LLM explanations)
- `OPENAI_BASE_URL` (optional; defaults to `https://api.openai.com/v1`)
- `MERCHANTOS_EMBEDDING_API_MODEL` (default `text-embedding-3-small`)
- `MERCHANTOS_LLM_MODEL` (default `gpt-4o-mini`)

## Important limitations
- Shopify, Trustpilot and Google adapters currently support merchant-authorized CSV exports only. Direct live platform integrations require each provider's supported API, credentials, scopes, review and approval; no scraping is implemented.
- TF-IDF fallback measures lexical similarity, not semantic meaning. The API returns the method used so the UI and operator can distinguish it from embedding-based similarity.
- Cluster membership is an exploratory signal, not proof of a shared cause.
- Sentiment labels are model/lexicon estimates and should not be used as financial authorization.
- Customer and transaction endpoints are not production multi-tenant/authenticated. Do not expose this build publicly with real customer data until authentication, tenant isolation, access controls and privacy controls are implemented.
- Manual matching records an association only. It does not authorize a refund. Existing refund eligibility and PayPal-side validation remain separate controls.

## Verification
- Python compilation: passed.
- JavaScript syntax check: passed.
- Automated tests: 17 passed.
- Tests cover CSV import, duplicate handling, analysis, customer investigation, transaction investigation, candidate lookup and exact manual matching.
- Tests use local seeded data and do not call live review providers, embedding APIs, LLMs or PayPal.
