# Database Architecture & Turso Compatibility Specification

## 1. Overview & Strategy

The platform employs a SQLite-compatible storage architecture:
- **Local Development & Testing**: Local SQLite database file (`local.db`) or in-memory (`:memory:`) using standard SQLAlchemy 2.x SQLite engine.
- **Production (Railway / Cloud)**: Turso Cloud (libSQL) using the official `libsql` Python driver and synchronous SQLAlchemy 2.x dialect.

---

## 2. Phase 0 Spike Findings & Technical Decisions

Per Section 5 of the project brief, a spike was conducted to determine driver compatibility:

### Spike Discoveries
1. **Legacy Dialect Incompatibility**: The `sqlalchemy-libsql` (0.2.0) package depends on `libsql-experimental`, which lacks pre-compiled wheels for modern Windows environments and requires Rust/MSVC compiler toolchains. Additionally, `libsql-experimental` has been superseded by the official `libsql` package (0.1.11+).
2. **DBAPI Parameter Variations**: The official `libsql` driver is DBAPI 2.0 compliant, but implements `_check_same_thread` (leading underscore) rather than `check_same_thread`.
3. **Function Registration**: Unlike standard SQLite, `libsql` connections do not expose `create_function()`. Standard SQLAlchemy `pysqlite` dialect attempts to register regex functions via `create_function()`, resulting in an `AttributeError`.

### Chosen Driver Strategy
- We utilize the official `libsql` package (`libsql>=0.1.11`).
- A clean SQLAlchemy dialect wrapper (`sqlite.libsql`) is provided in `backend/app/db/session.py`. It adapts `libsql`'s connection arguments and bypasses unsupported `create_function` calls while maintaining full statement caching, connection pooling, and transaction semantics.
- For local dev and tests, standard `sqlite:///` is used.
- For Turso production, the connection string follows `sqlite+libsql://[TURSO_DATABASE_URL]` with `connect_args={"auth_token": TURSO_AUTH_TOKEN}` or URL query parameters.

### Synchronous Engine Rationale
The libSQL Python bindings are synchronous. As mandated by the architecture guidelines, the backend uses a synchronous SQLAlchemy session with FastAPI route handlers. FastAPI executes synchronous route handlers in an optimized AnyIO worker threadpool, avoiding event loop blocking without introducing unstable async driver layers.

---

## 3. Database Schema Tables

The schema defines 15 core tables:
1. `roles`: System RBAC roles (`admin`, `analyst`, `viewer`).
2. `users`: Platform operators with Argon2 password hashes.
3. `customers`: Core business accounts with lifecycle status (`active`, `churned`, `paused`).
4. `customer_profiles`: Demographic, firmographic, and acquisition metadata.
5. `plans`: Subscription tiers, billing cycles, and prices in integer cents.
6. `subscriptions`: Active and historical customer subscriptions.
7. `transactions`: Successful and failed payments, refunds (amounts in minor units / cents).
8. `customer_activity`: High-frequency login sessions, feature usage, and durations.
9. `customer_events`: Lifecycle events (support tickets, payment failures, plan upgrades, cancellations).
10. `customer_segments`: Rule-based RFM segments (Champions, Loyal, At Risk, Dormant, New).
11. `predictions`: Historical batch and real-time model inferences and risk categories.
12. `ml_models`: Model registry storing task, version, algorithm, metrics JSON, threshold, and status.
13. `model_training_runs`: Background training execution tracking.
14. `model_artifacts`: Database-backed BLOB storage for joblib model pipelines (survives container redeployment).
15. `audit_logs`: Immutable trail of administrative actions, mutations, and logins.

---

## 4. Operational Workflows

### Local Development
```bash
# Run migrations to head
alembic upgrade head

# Generate deterministic synthetic seed data
python scripts/generate_seed.py

# Create first admin user
python -m app.cli create-admin --email admin@example.com --password AdminSecurePassword123!
```

### Turso Cloud Production Setup (Manual Human Steps)
1. Install Turso CLI:
   ```bash
   curl -sSfL https://get.tur.so/install.sh | bash
   ```
2. Log in and create database:
   ```bash
   turso auth login
   turso db create customer-intel-prod
   ```
3. Retrieve database URL and authentication token:
   ```bash
   turso db show customer-intel-prod --url
   # Example: libsql://customer-intel-prod-org.turso.io

   turso db tokens create customer-intel-prod
   ```
4. Configure production environment variables in Railway / container:
   - `ENVIRONMENT=production`
   - `TURSO_DATABASE_URL=libsql://customer-intel-prod-org.turso.io`
   - `TURSO_AUTH_TOKEN=<turso-jwt-token>`
   - `ARTIFACT_STORE=database`
5. Apply schema to Turso:
   ```bash
   turso db shell customer-intel-prod < database/schema.sql
   ```
   *Or execute `alembic upgrade head` with the Turso connection string configured.*
