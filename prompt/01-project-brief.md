# Customer Intelligence & Churn Prediction Platform — Project Brief

> This file is the **single source of truth** for all build stages. If a stage prompt and this brief disagree, this brief wins. If something here is wrong or impossible, stop, document the problem in the stage report, and choose the safest alternative. Never silently deviate.

---

## 1. Purpose

A production-quality portfolio project: a SaaS-style analytics product that helps a business manage customers, track subscriptions and revenue, analyze behavior, **predict churn**, **predict near-term revenue**, segment customers, compare ML models, and surface high-risk customers with actionable insight.

It must read as a serious real-world engineering project, not a tutorial. It is a **well-designed modular monolith**: one FastAPI app, one React app, one database.

## 2. Locked Architecture

| Layer | Choice | Hosting |
|---|---|---|
| Frontend | React + TypeScript (strict) + Vite + Tailwind CSS | Vercel |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic | Railway (Docker) |
| Database | SQLite-compatible; **Turso (libSQL)** in production, local SQLite file in dev/tests | Turso |
| ML | scikit-learn, pandas, numpy, joblib — inside the backend | Same as backend |

**Do not add:** microservices, Kubernetes, message brokers, Redis, event buses, or abstractions without a concrete need. Every technology must have a reason to exist.

### Priority order when requirements conflict
1. Security 2. Correctness 3. Maintainability 4. Testability 5. Simplicity 6. Performance 7. Developer experience

## 3. Engineering Rules (apply to every stage)

1. No pseudo-code, no `TODO` / `FIXME` / `...` / "implement this" placeholders, no "and so on".
2. No unresolved imports, no fake APIs, no screens disconnected from real backend endpoints, no invented DB columns.
3. Verify before claiming. **Never state that something works unless you ran it and saw it work.** Report real command output summaries.
4. Work incrementally: inspect the repo → write a plan → implement a phase → run lint/type-check/tests → fix → commit-ready state → next phase. Do not continue while build-breaking errors remain.
5. **Pin exact dependency versions** (lockfiles: `uv.lock` or pinned `requirements.txt` + `package-lock.json`). Before choosing versions or APIs of fast-moving libraries (Tailwind, TanStack Query, React Router, Pydantic, SQLAlchemy, libSQL drivers, Railway/Vercel config), **check current official documentation** and follow it rather than relying on memory.
6. No secrets in source, logs, tests, docs, or the frontend bundle. `.env.example` contains placeholders only.
7. Do not suppress lint/type errors without a written justification next to the suppression.
8. Dashboards must show real values from backend APIs. No hardcoded demo statistics in app code.

## 4. Backend Architecture

```
backend/
├── app/
│   ├── main.py
│   ├── cli.py                     # create-admin, train, score, seed helpers
│   ├── core/                      # config, security, logging, exceptions, middleware
│   ├── api/
│   │   ├── dependencies.py
│   │   └── v1/                    # auth, users, customers, subscriptions, transactions,
│   │                              # analytics, predictions, ml
│   ├── db/                        # engine/session, base
│   ├── models/                    # SQLAlchemy ORM
│   ├── schemas/                   # Pydantic v2 API contracts (never expose ORM objects)
│   ├── repositories/              # persistence only
│   ├── services/                  # business logic only
│   ├── ml/
│   │   ├── datasets/              # synthetic generator, dataset builder
│   │   ├── features/              # ONE feature-engineering implementation
│   │   ├── preprocessing/         # sklearn ColumnTransformer pipelines
│   │   ├── models/                # MLModel protocol + 5 implementations
│   │   ├── training/
│   │   ├── evaluation/
│   │   ├── inference/
│   │   └── registry/              # ModelRegistry + ArtifactStore implementations
│   └── utils/
├── tests/
├── alembic/  + alembic.ini
├── scripts/                       # export_openapi.py, generate_seed.py
├── artifacts/                     # dev-only, git-ignored
├── pyproject.toml, requirements*.txt / uv.lock
└── Dockerfile
```

**SOLID, concretely**
- Routes: HTTP concerns only. Services: business logic. Repositories: persistence. ML services: ML operations.
- `MLModel` is a `Protocol`; `LogisticRegressionModel`, `KNNModel`, `RandomForestClassifierModel`, `LinearRegressionModel`, `RandomForestRegressorModel` conform to it. Routes never import concrete model classes.
- Services depend on repository/`ArtifactStore`/`ModelRegistry` abstractions, injected via FastAPI dependencies.
- No giant service classes: `CustomerService`, `SubscriptionService`, `AnalyticsService`, `PredictionService`, `TrainingService`, `FeatureEngineeringService`, `ModelRegistry`, `SegmentationService`.

## 5. Database

- Must work with an **empty** database and with seeded data.
- Repository contains executable `database/schema.sql` and `database/seed.sql` (real SQL, not descriptions).
- Use PKs, FKs, UNIQUE, NOT NULL, CHECK constraints, indexes on filter/join columns, `created_at`/`updated_at`, sensible `ON DELETE` behavior. Remember SQLite needs `PRAGMA foreign_keys = ON` per connection.
- Avoid PostgreSQL-only features. Store money as integer minor units (e.g. cents) with a currency column or a single documented currency.

### Tables (adjust only with justification, documented in `docs/database.md`)

`roles`, `users`, `customers`, `customer_profiles`, `plans`, `subscriptions`, `transactions`, `customer_activity` (logins/usage sessions), `customer_events` (support tickets, payment failures, plan changes, cancellations), `customer_segments`, `predictions`, `ml_models`, `model_training_runs`, `model_artifacts` (BLOB storage for production), `audit_logs`.

### Turso / libSQL compatibility — Phase 0 spike (mandatory)
Do **not** assume a SQLAlchemy ⇄ Turso path works. First build a tiny spike and prove:
1. SQLAlchemy engine connects to local SQLite (dev/tests).
2. SQLAlchemy engine connects to Turso using the **currently recommended** libSQL driver/dialect (check official Turso docs and the dialect's README).
3. Alembic migrations run locally; and you know exactly how they are applied to Turso.

Fallbacks, in order, if (2) fails: (a) the libSQL Python client with SQLAlchemy Core only, (b) embedded-replica approach, (c) apply Alembic-generated SQL to Turso via the Turso CLI/SQL runner while the app uses a verified driver. Record the decision and its limits in `docs/database.md`. Prefer a **synchronous** SQLAlchemy engine if libSQL drivers are sync-only (use sync route handlers/threadpool); "async where appropriate" does not mean forcing async onto a sync driver.

**Schema source of truth:** `schema.sql` and Alembic migrations must produce equivalent schemas. Add a test that builds both and compares tables, columns, indexes, and FKs.

**Seed data:** `seed.sql` is generated by a deterministic script (`backend/scripts/generate_seed.py`, fixed random seed) and committed. ~200 clearly synthetic customers, 12–24 months of history, multiple plans. **No users with credentials in seed data.** Demo users are created via `python -m app.cli create-admin` / `create-user` with passwords supplied at runtime.

## 6. Data Definitions (leakage control — read carefully)

All ML datasets are built **as of a snapshot date `T`**. Features may only use data with timestamp **≤ T**. Labels use data strictly **after T**.

- **Panel dataset:** one row per (customer, monthly snapshot). Customers already churned at `T`, or not yet created at `T`, are excluded from that snapshot.
- **Churn label `churned_30d`:** 1 if the customer's subscription was cancelled/churned in `(T, T+30d]`, else 0.
- **Revenue target `future_revenue_90d`:** sum of **successful** transaction amounts in `(T, T+90d]` (≥ 0, minor units). Churned-during-window customers legitimately contribute their pre-churn revenue.
- **Split:** temporal. Earliest snapshots → train, middle → validation, latest complete snapshots → test. Snapshots whose label window extends beyond available data are excluded from training/eval (but may be used for live scoring). Document that the same customers appear across splits (temporal validation) and why that is acceptable.
- **No label-derived features.** `customers.status`, `churned_at`, cancellation events after `T`, and the churn prediction itself must never be features. The revenue model must not use the churn prediction as a feature.
- **Dataset versioning:** `dataset_version` = deterministic hash of (generator seed, snapshot list, feature_version, row count). `feature_version` is a constant bumped when feature logic changes.

### Features (one shared implementation for training AND inference)

`tenure_days`, `monthly_revenue`, `total_revenue_to_date`, `transaction_count_90d`, `avg_transaction_value_90d`, `days_since_last_activity`, `activity_count_30d`, `activity_count_90d`, `login_frequency_30d`, `support_ticket_count_90d`, `payment_failure_count_90d`, `engagement_score`, `subscription_length_days`, categoricals: `plan_tier`, `billing_cycle`, `acquisition_channel`, `region`.

- A single `FeatureEngineeringService` computes features from raw tables for a customer/snapshot. Training and inference both call it. Ad-hoc prediction (the Prediction page) accepts the **raw feature inputs** directly and validates them with Pydantic; the schema and feature order come from one place.
- Preprocessing (`SimpleImputer`, `StandardScaler`, `OneHotEncoder(handle_unknown="ignore")` in a `ColumnTransformer`) lives **inside** the sklearn `Pipeline` that is serialized with the model, so inference can never drift from training.

### Synthetic data
Generated by `backend/app/ml/datasets/generate.py` with a fixed seed, clearly documented as **synthetic**. It must embed real structure (e.g. churn probability rises with payment failures, support tickets, and inactivity, and falls with engagement and tenure; revenue depends on plan and activity) with noise, so models learn something but aren't trivially perfect. Document the generating process in `docs/ml.md`.

## 7. Machine Learning

| Task | Algorithms | Primary metrics |
|---|---|---|
| Churn classification | Logistic Regression, KNN, Random Forest | Precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix (accuracy reported but not optimized) |
| Revenue regression | Linear Regression, Random Forest Regressor | MAE, MSE, RMSE, R² |

- **Class imbalance:** `class_weight="balanced"` where supported; for KNN use distance weighting and threshold tuning. Choose the decision threshold on the **validation** set (documented objective, e.g. maximize F1 or target recall); store it in model metadata.
- **KNN has two real purposes:** (1) a churn classifier for comparison (scaled features — it's distance-based), and (2) **similar customers**: `GET /api/v1/ml/customers/{id}/similar` returns the k nearest customers (in the scaled feature space) with their outcomes, so analysts can reason by analogy. Explain this in `docs/ml.md`.
- **Segments** are rule-based (RFM-style: Champions, Loyal, New, At Risk, Dormant), computed with SQL/service logic from configurable rules. No extra ML needed.
- Deterministic seeds everywhere (`random_state`), recorded in metadata.
- Models are trained **explicitly** (CLI or endpoint), never inside prediction requests. Loaded models are cached in memory per process and invalidated on activation.

### Model registry
`ml_models` rows store: name, task (`churn`/`revenue`), algorithm, version (e.g. `churn_logistic_v1`), training date, dataset_version, feature_version, metrics (JSON), decision threshold (churn), status (`candidate` | `active` | `archived`), artifact key.
- Training creates a `candidate`; it **never** auto-replaces the active model. Activation is an explicit admin action (`POST /ml/models/{id}/activate`), allowed only if the model's `feature_version` matches the current code.
- Exactly one active model per task.

### Artifact storage
`ArtifactStore` protocol with:
- `LocalFileArtifactStore` — dev and tests (`backend/artifacts/`, git-ignored).
- `DatabaseArtifactStore` — **production default**: serialized joblib bytes in the `model_artifacts` table (Turso). Railway container disks are ephemeral, so local-file artifacts would vanish on redeploy.
- Selected by config (`ARTIFACT_STORE=local|database`). The design must let an S3-style store be added later without touching ML services. Document artifact size limits and the S3 upgrade path.
- Safety: only load artifacts this application wrote (registry-referenced keys); never unpickle user-supplied files. Optionally store and verify a SHA-256 checksum.

On first production deploy there is no active model: the app must start fine and return a clear `MODEL_NOT_AVAILABLE` error on prediction endpoints, and `python -m app.cli train-all --activate` (or the admin endpoint) bootstraps models.

### Training execution
Training is small, but HTTP requests must not hang: `POST /ml/train/*` creates a `model_training_runs` row (`queued`→`running`→`succeeded`/`failed`), runs via FastAPI background task, and the client polls `GET /ml/training-runs/{id}`. Run a single uvicorn worker (documented) so background state is consistent.

### Risk categories
Backend interprets churn probability into `low` / `medium` / `high` using thresholds from settings (defaults: medium ≥ 0.30, high ≥ 0.60; overridable via env). The frontend only displays the category returned by the API; it never hardcodes thresholds.

## 8. Authentication & Authorization

- Argon2 password hashing (e.g. `argon2-cffi`/`pwdlib`); JWT access tokens (short-lived, `ACCESS_TOKEN_EXPIRE_MINUTES`), secret from env; reject startup in production if `JWT_SECRET_KEY` is missing/weak.
- `POST /auth/register` always creates a **`viewer`**. Only admins can change roles. The first admin is created via CLI.
- Rate-limit `/auth/login` and `/auth/register` (e.g. `slowapi`; per-process limits are acceptable and must be documented as such).
- Generic login failure messages (no user enumeration).

| Capability | admin | analyst | viewer |
|---|---|---|---|
| Manage users/roles | ✅ | ❌ | ❌ |
| Customers/subscriptions/transactions: create/update/delete | ✅ | ✅ | ❌ |
| Customers etc.: read | ✅ | ✅ | ✅ (read-only) |
| Analytics & dashboards: read | ✅ | ✅ | ✅ |
| Train models, run scoring, ad-hoc predict | ✅ | ✅ | ❌ |
| Activate/archive models | ✅ | ❌ | ❌ |
| View predictions & model metrics | ✅ | ✅ | ✅ |
| Audit logs | ✅ | ❌ | ❌ |

Write audit log entries for logins, role changes, customer mutations, model training/activation.

## 9. API Surface (all under `/api/v1`, plus ops routes)

```
Ops:        GET /health   GET /ready            (ready checks DB; no infra details)
Auth:       POST /auth/register  POST /auth/login  GET /auth/me
Users:      GET /users  GET|PATCH /users/{id}                         (admin)
Customers:  GET|POST /customers   GET|PATCH|DELETE /customers/{id}
            GET /customers/{id}/activity | /transactions | /subscriptions | /events
Plans:      GET /plans
Subs:       GET|POST /subscriptions   GET|PATCH /subscriptions/{id}
Txns:       GET|POST /transactions
Analytics:  GET /analytics/overview | /revenue | /churn | /customers | /segments | /activity
Predictions:GET /predictions            (stored; filter by risk, customer; paginated)
            GET /predictions/high-risk
ML:         POST /ml/train/churn   POST /ml/train/revenue
            GET /ml/training-runs/{id}
            GET /ml/models   GET /ml/models/{id}
            POST /ml/models/{id}/activate   POST /ml/models/{id}/archive
            GET /ml/model-comparison?task=churn|revenue
            POST /ml/predict/churn   POST /ml/predict/revenue     (ad-hoc, raw feature input)
            GET /ml/customers/{id}/prediction
            GET /ml/customers/{id}/similar
            POST /ml/score-customers          (batch score → stores predictions)
```

Required behaviors: pagination (`page`, `page_size` with max), filtering, sorting (allow-listed fields only), consistent status codes, request IDs (`X-Request-ID`), OpenAPI at `/docs`, `/redoc`, `/openapi.json` with useful descriptions. Analytics use **SQL aggregation**, not fetch-all-then-loop in Python. Avoid N+1 queries.

### Error format
```json
{ "success": false, "error": { "code": "CUSTOMER_NOT_FOUND", "message": "Customer was not found" }, "request_id": "..." }
```
Centralized handlers; no stack traces to clients; internal exceptions logged server-side without secrets.

## 10. Security Baseline

Password hashing; JWT hardening (algorithm pinned, expiry enforced); Pydantic validation on all input; parameterized queries only; strict CORS (dev: `http://localhost:5173`; prod: only configured origins; **never** `*` in production); security headers; allow-listed sort fields; audit logging; rate limiting on auth; no sensitive data in logs (passwords, tokens, DB credentials); debug off in production; non-root Docker user.

## 11. Logging & Observability

Structured (JSON) logs with request ID, method, path, status, duration; business events (customer mutations, ML training start/finish with run id). Provide an error-tracking hook (e.g. optional `SENTRY_DSN`) without requiring it.

## 12. Environment Variables

Backend `.env.example`:
```
ENVIRONMENT=development
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./local.db
TURSO_DATABASE_URL=
TURSO_AUTH_TOKEN=
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=http://localhost:5173
ARTIFACT_STORE=local
ARTIFACT_LOCAL_DIR=./artifacts
RISK_THRESHOLD_MEDIUM=0.30
RISK_THRESHOLD_HIGH=0.60
SENTRY_DSN=
```
Frontend `.env.example`: `VITE_API_BASE_URL=` (client-visible — **never** put secrets in `VITE_*`).

## 13. Frontend Summary (details in Stage 2)

React + TypeScript strict (no `any` without justification), Vite, Tailwind, React Router, TanStack Query for server state, React Hook Form + Zod, Recharts. **API types are generated from the backend OpenAPI schema** (`openapi-typescript` or equivalent) — never hand-duplicated. CI fails if generated types are out of date.

## 14. Definition of Done (whole project)

- Backend: `ruff check`, `ruff format --check`, `mypy`, `pytest` all pass.
- Frontend: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` all pass.
- `/health`, `/ready`, `/docs` verified against a running server.
- Frontend verified against the **real** local backend: register, login, protected routes, customer list/detail, analytics, prediction, model metrics, errors, loading states, logout.
- Docker images build; `docker compose up` works; CI workflows are valid.
- Docs complete and commands in them actually match the repo.
- Final security review done and findings fixed.
- Honest `docs/implementation-report.md` including known limitations.
