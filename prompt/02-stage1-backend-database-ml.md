# STAGE 1 — Database, Backend, Authentication, Analytics, and Machine Learning

You are acting as a Principal Software Architect, Senior Backend Engineer, ML Engineer, Database Architect, and Security Engineer.

## Your inputs

Read `docs/project-brief.md` completely before doing anything else. It is the single source of truth for architecture, data definitions, API surface, security rules, and engineering rules. If this prompt and the brief conflict, the brief wins.

## Your scope

Build **only** the database, backend, and ML system, to a verified, runnable state. Do **not** build the frontend in this stage (Stage 2) or Docker/CI/deployment docs (Stage 3), except for the small items listed under Phase 10.

## How to work

1. Inspect the repository.
2. Write an implementation plan (list the files and modules you will create, per phase). Pause for review if your environment supports plan approval.
3. Implement one phase at a time. After **each** phase: run the relevant tests, `ruff check`, `ruff format --check`, and `mypy`; fix failures; verify imports; only then continue.
4. Never claim something works unless you executed it and saw the result.

---

## Phase 0 — Repository bootstrap and Turso spike

- Create the repo layout from the brief (`backend/`, `database/`, `docs/`, `.gitignore`, `LICENSE` (MIT), root `README.md` stub).
- `.gitignore` must exclude: `.env`, `*.db`, `backend/artifacts/`, `__pycache__/`, `node_modules/`, `.venv/`, build output.
- Set up Python 3.12+ project with `pyproject.toml`, pinned dependencies, Ruff, MyPy (strict-leaning config), pytest, pytest-asyncio (only if you use async), pre-commit.
- **Turso spike (required):** following brief §5, prove the SQLAlchemy connection path for local SQLite and for Turso, and how Alembic migrations reach Turso. Use the current official Turso/libSQL documentation. If you cannot reach a real Turso database from this environment, say so plainly: verify what you can locally, implement the most likely correct path, and list exactly what the human must verify manually. Record the decision, fallbacks tried, and limitations in `docs/database.md`.

**Gate:** the spike result is written down and the chosen driver strategy is unambiguous.

## Phase 1 — Schema, migrations, and seed pipeline

- Write `database/schema.sql` (executable) covering every table in the brief with constraints and indexes.
- Write SQLAlchemy models that match it exactly.
- Create Alembic config and an initial migration. Document `alembic upgrade head`.
- Add a test that builds a DB from `schema.sql` and from Alembic, then compares tables/columns/indexes/foreign keys.
- Implement `backend/scripts/generate_seed.py` (deterministic) and generate `database/seed.sql` (~200 synthetic customers, 12–24 months of subscriptions, transactions, activity, events, plans; churn outcomes consistent with the brief's data definitions). Verify `seed.sql` loads into a fresh DB created from `schema.sql`, and that the app also starts on an empty DB.
- Write `docs/database.md` (relationships, decisions, Turso workflow: create DB, get URL, create token, apply schema/seed, local dev, production connection).

**Gate:** schema ⇄ migration equivalence test passes; seed loads; foreign key check (`PRAGMA foreign_key_check`) is clean.

## Phase 2 — Backend foundation

- `core/config.py` (pydantic-settings; validates production requirements such as a strong `JWT_SECRET_KEY` and non-wildcard CORS), `core/logging.py` (structured JSON), `core/exceptions.py` (domain exceptions + centralized handlers producing the brief's error format), request-ID middleware, request logging middleware (method, path, status, duration), security-headers middleware, CORS from config.
- DB session management and dependency injection.
- `GET /health` (process only) and `GET /ready` (checks DB connectivity, reveals no infrastructure details).
- App factory in `main.py`; OpenAPI metadata (title, description, tags).

**Gate:** server starts; `/health`, `/ready`, `/docs`, `/openapi.json` respond; errors use the standard format; tests cover them.

## Phase 3 — Authentication and authorization

- Argon2 hashing, JWT creation/verification, `get_current_user`, role-based dependency guards implementing the brief's permission matrix.
- Endpoints: `register` (always `viewer`), `login`, `me`; `users` list/get/patch (admin only, role changes audited).
- Rate limiting on auth endpoints. Generic login errors.
- CLI: `python -m app.cli create-admin` and `create-user` (password prompted or read from an env var at runtime; never stored in repo).
- Audit log writes for login, role change.

**Gate:** tests for successful login, invalid login, missing/expired/tampered token, viewer-cannot-write, admin-only routes, register-cannot-escalate. All pass.

## Phase 4 — Customer, subscription, and transaction APIs

- Repositories → services → routes for customers (+ profile), plans, subscriptions, transactions, and the customer sub-resources (activity, transactions, subscriptions, events).
- Pydantic v2 schemas with constrained fields, enums, validators. Pagination, filtering, allow-listed sorting.
- Audit log on customer mutations.

**Gate:** CRUD tests, pagination tests, invalid-input tests, 404/403/401 behaviors, no N+1 (assert query counts in at least one list test).

## Phase 5 — Analytics and segmentation

- SQL-aggregated endpoints: `overview` (total customers, active customers, churn rate, total/average revenue, high-risk count, active-model summary), `revenue` (trend over time), `churn` (trend), `customers` (distribution), `segments`, `activity` (trend).
- `SegmentationService` with rule-based RFM-style segments; thresholds in config.
- Handle empty database gracefully (zeros/empty series, not errors).

**Gate:** analytics tests against seeded data with hand-verified expected numbers for at least `overview`, plus empty-DB tests.

## Phase 6 — Synthetic dataset and feature engineering

- `ml/datasets/generate.py` (deterministic, structured relationships + noise, documented as synthetic) shared by the seed script where sensible.
- `FeatureEngineeringService`: as-of-snapshot feature computation straight from DB tables, honoring the brief's leakage rules. Also a pure function layer so ad-hoc prediction can reuse the same feature schema/order.
- Dataset builder: panel of (customer, snapshot) rows with `churned_30d` and `future_revenue_90d`, `dataset_version`, `feature_version`, temporal train/val/test split.
- **Leakage tests:** prove that changing data after snapshot `T` does not change features at `T`; prove excluded customers are excluded; prove label windows are correct on a tiny hand-built fixture.

**Gate:** leakage and feature tests pass.

## Phase 7 — Training, evaluation, registry, artifact storage

- `MLModel` protocol + five implementations; sklearn `Pipeline`s with `ColumnTransformer` preprocessing serialized with each model.
- Training service: fits on train, selects threshold on validation (churn), evaluates on test, stores metrics (classification: accuracy, precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix; regression: MAE, MSE, RMSE, R²), records seeds and versions.
- `ModelRegistry` + `ArtifactStore` (`LocalFileArtifactStore`, `DatabaseArtifactStore`) per the brief; checksum verification; candidate/active/archived lifecycle; explicit activation with feature-version check.
- CLI: `python -m app.cli train-all [--activate]`.
- Training runs table + background execution.

**Gate:** tests for preprocessing, training determinism (same seed → same metrics), serialization round-trip for **both** artifact stores, registry lifecycle, activation rules, invalid feature values. Report real metrics from a real training run and confirm they are plausible (better than a trivial baseline; not suspiciously perfect — if AUC ≈ 1.0, investigate leakage).

## Phase 8 — ML inference and ML/prediction APIs

- Inference service with in-memory model cache invalidated on activation; no training in request paths.
- Implement every `/ml/*` and `/predictions*` endpoint in the brief, including model comparison, ad-hoc prediction with raw feature input, per-customer prediction, similar customers (KNN), and batch scoring that stores predictions and returns `risk_category` computed from config thresholds.
- Clear `MODEL_NOT_AVAILABLE` error when no active model exists.

**Gate:** API tests for prediction success, missing model, validation errors, comparison, role restrictions (viewer cannot train/predict ad-hoc; only admin can activate).

## Phase 9 — Contract export

- `backend/scripts/export_openapi.py` writes `backend/openapi.json` deterministically (sorted, stable). This file is the contract Stage 2 consumes. Commit it.
- Verify every route in the brief exists in the OpenAPI document (write a test that asserts this).

## Phase 10 — Backend quality pass

- Review for N+1 queries, missing indexes, missing authorization checks, sensitive logging, plaintext secrets, unsafe artifact loading.
- Make sure `ruff check`, `ruff format --check`, `mypy`, and `pytest` pass cleanly. Do not pad tests; prefer meaningful behavior tests.
- Write `docs/ml.md` (problem definitions, features, leakage controls, KNN rationale, metrics, synthetic data caveat) and a first pass of `docs/api.md`.

---

## Exit criteria for Stage 1

All of these must be true **and verified by running them**:

1. `ruff check`, `ruff format --check`, `mypy`, `pytest` pass.
2. Fresh local DB from `schema.sql` + `seed.sql` works; an empty DB also works; Alembic upgrade works.
3. `python -m app.cli create-admin` works; login returns a token; protected routes enforce the permission matrix.
4. `python -m app.cli train-all --activate` trains all five models, registers them, and activates the best candidate per task; predictions work through the API.
5. `/health`, `/ready`, `/docs`, `/openapi.json` work; `backend/openapi.json` is exported.

## Deliverable: `docs/stage1-report.md`

Include: what was built; the Turso spike outcome and any manual verification still required; exact commands to run backend, tests, migrations, seed, training; model metrics table (from a real run) with a short honest interpretation; known limitations; anything that deviated from the brief and why. Do not claim unverified items as verified.
