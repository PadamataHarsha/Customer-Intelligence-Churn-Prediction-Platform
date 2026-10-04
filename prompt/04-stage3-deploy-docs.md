# STAGE 3 — Containers, CI/CD, Deployment Config, Documentation, Final Security Review

You are acting as a DevOps Engineer, Security Engineer, and Technical Writer.

## Your inputs

Read `docs/project-brief.md`, `docs/stage1-report.md`, and `docs/stage2-report.md`, then inspect the whole repository. Both the backend and frontend already exist and pass their own checks. Do not rewrite application features; fix bugs you find minimally and record them.

## How to work

Inspect → plan → implement phase by phase → verify by actually running things. Never claim a deployment config works if you only wrote it. Where something can only be verified on Railway, Vercel, or Turso by the human (you likely cannot reach those accounts), say so explicitly and provide the exact manual verification steps. Check **current official documentation** for Railway, Vercel, and Turso configuration before writing config.

---

## Phase D1 — Docker

- `backend/Dockerfile`: slim Python 3.12 image, dependency layer caching, non-root user, no dev dependencies, production server command (`uvicorn` bound to `0.0.0.0` using `${PORT:-8000}`), **single worker** (the app uses in-process model cache and background training), healthcheck. `.dockerignore`.
- `frontend/Dockerfile`: multi-stage (build → static server such as nginx or similar) with SPA fallback routing; build-time `VITE_API_BASE_URL` argument. `.dockerignore`.
- `docker-compose.yml` for local use: backend (SQLite volume, `ARTIFACT_STORE=local` or `database`), frontend, env via `.env` files. Document how to create the first admin inside the container and how to train/activate models.
- **Verify:** `docker build` both images and `docker compose up`; hit `/health`, `/ready`, and the frontend. If Docker isn't available in your environment, say so and list what remains unverified.

## Phase D2 — CI (GitHub Actions)

- `.github/workflows/backend.yml`: install (cached), `ruff check`, `ruff format --check`, `mypy`, `pytest`; also run the OpenAPI export and **fail if `backend/openapi.json` differs from the committed file**.
- `.github/workflows/frontend.yml`: install (`npm ci`), lint, typecheck, test, build, and `check:api-types` (fail on contract drift).
- Least-privilege `permissions`, pinned action versions, dependency caching, concurrency cancellation for superseded runs. No secrets in workflow files; tests must not need real Turso credentials.
- Validate YAML syntax and reproduce each job's commands locally.

## Phase D3 — Railway (backend)

- Create the Railway config for the backend service. Because Railway config-as-code file location relative to the service **root directory** has specific rules, check the current docs and place `railway.toml` accordingly (the brief suggests `backend/railway.toml` with root directory `backend`); document the exact "config file path" setting if one is needed.
- Config must: build from the Dockerfile, set `healthcheckPath = "/health"`, restart policy, and rely on Railway's `$PORT`.
- Production environment: `ENVIRONMENT=production`, `ARTIFACT_STORE=database`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, strong `JWT_SECRET_KEY`, `CORS_ORIGINS` set to the exact Vercel origin(s), no wildcard.
- Document the **first-deploy bootstrap** (schema applied to Turso → create admin → `train-all --activate`) and how to run those CLI commands against production (Railway shell/one-off command or a documented alternative), without putting secrets in files.
- Document why a single worker and why model artifacts live in the database rather than on the container disk.

## Phase D4 — Vercel (frontend)

- `frontend/vercel.json` **is required** for React Router client-side routing: add the SPA rewrite to `index.html` (exclude asset paths appropriately). Add only what is needed.
- Document: connect repo, set root directory `frontend`, framework preset Vite, build command, output directory `dist`, set `VITE_API_BASE_URL` to the Railway backend URL (set in Vercel, not committed), redeploy, then add the resulting Vercel domain to backend `CORS_ORIGINS`. Mention preview deployments and CORS (preview URLs change; document the policy chosen, e.g. only production origin, or an explicit allow-list).

## Phase D5 — Turso operations docs

Update `docs/database.md` with exact, current CLI steps: install CLI, authenticate, create database, get URL, create token, apply `database/schema.sql`, (optional) apply `database/seed.sql`, how Alembic migrations are applied to Turso given the Stage 1 spike decision, local development with SQLite, and how production connects. Mark any step you could not run yourself as "not verified by the author".

## Phase D6 — Documentation

Create or finalize:
- `README.md`: overview, features, architecture diagram (Mermaid), stack, screenshot placeholders (or real screenshots if they exist), local development (backend, frontend, database, first admin, ML training), testing, Docker, deployment (Railway, Vercel, Turso), environment variables table, API docs location, troubleshooting. **Someone who clones the repo must be able to run it by following the README** — test this by following your own README from a clean clone/venv.
- `docs/architecture.md`: modular-monolith rationale, layering, SOLID in practice, auth/token decision and trade-offs, data flow (Mermaid).
- `docs/api.md`, `docs/database.md`, `docs/ml.md`: finalize, ensuring every command and route matches the code.

## Phase D7 — Security review

Review and fix, with evidence, each of: hardcoded credentials; plaintext passwords; weak/missing JWT secret handling; JWT algorithm pinning and expiry; insecure CORS; SQL injection (parameterization, sort-field allow-listing); missing authorization checks (walk every route against the permission matrix); sensitive data in logs; exposed secrets in the frontend bundle (`VITE_*`); unsafe model-artifact loading; debug mode in production; rate limiting on auth; security headers; dependency vulnerabilities (run `pip-audit` / `npm audit` and triage); Docker non-root. List each finding and resolution in the report; unresolved items go under known limitations.

## Phase D8 — Final validation

Run and report real results for:
```
cd backend && ruff check . && ruff format --check . && mypy . && pytest
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build && npm run check:api-types
```
Then start the stack (compose or local) and verify `GET /health`, `GET /ready`, `GET /docs`, and a login → dashboard → prediction flow against the real backend.

---

## Exit criteria for Stage 3

1. Both Docker images build; compose stack runs (or the gap is stated honestly).
2. CI workflows are valid and reproduce locally, including the contract-drift check.
3. Railway/Vercel/Turso instructions are complete, current, and clearly separate "verified here" from "must be verified by the human".
4. README works from a clean clone.
5. Security review completed with findings fixed or documented.
6. No secrets anywhere in the repository (scan for it).

## Deliverable: `docs/implementation-report.md`

Architecture summary; technology choices and why; database design; API summary; ML algorithms and **real** model metrics with honest interpretation; frontend architecture; security decisions and review findings; testing summary (counts and what they cover); deployment instructions summary; a "Verified vs. not verified" table; known limitations (e.g. synthetic data, per-process rate limiting, single-worker constraint, DB-stored artifacts size limits); future improvements (S3 artifact store, refresh tokens/httpOnly cookies, real data connectors, scheduled retraining).

Finish with a concise final message: what was built, repo structure, how to run locally, ML training commands, deployment steps, env vars, test commands, key decisions, and limitations that genuinely remain.
