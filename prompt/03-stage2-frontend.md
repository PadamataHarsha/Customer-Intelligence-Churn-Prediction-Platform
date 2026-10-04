# STAGE 2 — Frontend

You are acting as a Senior Frontend Engineer and Product Designer building a professional SaaS analytics UI.

## Your inputs

1. Read `docs/project-brief.md` completely.
2. Read `docs/stage1-report.md` and `backend/openapi.json`. The backend is **already built**. Treat `openapi.json` as the contract.
3. Do **not** modify backend behavior in this stage unless you find a genuine bug; if you do, fix it minimally, add a regression test, regenerate `backend/openapi.json`, and list the change in the stage report.

## Scope

Build `frontend/` only (plus tiny root-level glue such as scripts). No Docker, CI, or deployment work (Stage 3).

## How to work

Inspect the repo → write a plan → implement phase by phase. After each phase run lint, type-check, tests, and build; fix before continuing. From Phase F4 onward, **run the real backend locally** (local SQLite, seeded, models trained and activated, an admin user created via CLI) and verify screens against it. Never claim a screen works unless you loaded it against the running backend.

---

## Phase F0 — Setup

- Vite + React + TypeScript with `strict: true` (+ `noUncheckedIndexedAccess`), Tailwind CSS (use the current stable setup per official docs), React Router, TanStack Query, React Hook Form, Zod, Recharts, ESLint, Prettier, Vitest + Testing Library (+ MSW for **tests only**).
- Pinned versions with lockfile. `package.json` scripts: `dev`, `build`, `lint`, `typecheck`, `test`, `format`, `generate:api`.
- `.env.example` with `VITE_API_BASE_URL=`. Remember it is client-visible; no secrets.
- Avoid `any`; if unavoidable, add a justification comment.

## Phase F1 — API contract and client

- `generate:api` generates TypeScript types from `../backend/openapi.json` (e.g. `openapi-typescript`) into `src/types/api.generated.ts`. Commit the output.
- Add a script/check (`npm run check:api-types`) that regenerates and fails if the committed file differs — Stage 3 wires this into CI.
- Centralized, typed API client in `src/services/api/`: base URL from env, auth header injection, standard error-format parsing (`error.code`, `error.message`, `request_id`), `401` handling (clear session, redirect to login), request cancellation via `AbortSignal`, limited retry only for safe idempotent GETs and network errors.
- One typed function per endpoint used; TanStack Query hooks per feature with sensible query keys, stale times, and cache invalidation after mutations.

## Phase F2 — Auth

- Login and Register pages (React Hook Form + Zod; accessible labels and errors).
- Token strategy: keep the access token in memory with `sessionStorage` persistence for reload survival; document the XSS/CSRF trade-off and why this was chosen in `docs/architecture.md` notes (Stage 3 will finalize docs). Never use `localStorage` for tokens.
- `AuthProvider`, `ProtectedRoute`, role-aware route guard (e.g. hide/disable write actions for `viewer`, ML training for non-admin/analyst), logout, expired-token handling.

## Phase F3 — Layout and design system

- Professional SaaS look: sidebar nav, top bar (user menu, logout), responsive (desktop-first, usable on mobile), consistent spacing/typography via design tokens (CSS variables / Tailwind theme). Light theme required; dark theme optional if it doesn't compromise quality.
- Reusable `ui/` components: Button, Input, Select, Card, Badge (risk colors: never rely on color alone — include text/icon), Table, Pagination, Modal/Dialog, Tabs, Toast, Skeleton, EmptyState, ErrorState, Spinner.
- Accessibility: semantic HTML, labeled controls, visible focus states, keyboard navigation, adequate contrast, text alternatives or data-table fallbacks for charts.

## Phase F4 — Dashboard

- KPI cards (total customers, active customers, churn rate, total revenue, average revenue, high-risk customers, active-model performance).
- Revenue trend chart, churn trend chart, segment breakdown, high-risk customers table, model performance panel.
- All values from `/analytics/*`, `/predictions/high-risk`, `/ml/models`. Loading skeletons, empty states (e.g. no active model → helpful message), error states with retry.

## Phase F5 — Customers

- List with debounced search, filters, sortable columns (only backend allow-listed fields), pagination (server-side), URL-synced query params.
- Customer detail: profile, subscriptions, transactions, activity timeline, events, revenue summary, prediction card (probability, classification, risk category, predicted revenue, model version), **similar customers** panel.
- Create/Edit forms (analyst/admin only) with Zod validation matching backend constraints; delete with confirmation; toasts on success/failure; optimistic UI only where safe.

## Phase F6 — Analytics page

- Revenue trends, churn trends, customer distribution, subscription/plan distribution, activity trends, segments. Range controls only if the backend supports them. Charts must have titles, axis labels, tooltips, and an accessible data-table alternative.

## Phase F7 — ML dashboard

- Models list by task with status (candidate/active/archived), version, training date, dataset/feature version, metrics.
- Model comparison view (`/ml/model-comparison`): side-by-side metrics table + chart; highlight best per metric; show churn threshold.
- Training: buttons (analyst/admin) to start churn/revenue training → show run status by polling `/ml/training-runs/{id}` until finished, with success/failure feedback. Activation/archive (admin only) with confirmation, showing the registry rules' error messages.
- Batch scoring trigger (analyst/admin) with result feedback.

## Phase F8 — Prediction page

- Form for raw feature inputs (labels, units, sensible bounds from the generated schema/Zod), submit → churn probability, churn classification, risk category (as returned by the backend), predicted revenue, and which model versions produced them. Handle `MODEL_NOT_AVAILABLE` and validation errors clearly.

## Phase F9 — Performance and polish

- Route-level code splitting (`React.lazy`), query caching, pagination everywhere, memoization only where measured/justified.
- 404 page, global error boundary, consistent empty/loading/error patterns.

## Phase F10 — Tests and quality

- Unit tests: utilities, formatters, Zod schemas, auth guard logic.
- Component/flow tests with MSW (tests only): login success/failure, protected redirect, customer list search/pagination, create-customer validation, prediction form happy path and `MODEL_NOT_AVAILABLE`, viewer cannot see write actions.
- Make `lint`, `typecheck`, `test`, `build` pass cleanly.

## Phase F11 — Real integration verification

With the real backend running locally, manually verify (and record results): register, login, protected route redirect, dashboard load, customer list/detail, create/edit customer as analyst, viewer restrictions, analytics, ML dashboard metrics and comparison, a training run, ad-hoc prediction, error display, logout. If you can drive a browser, capture screenshots into `docs/screenshots/`; otherwise state that screenshots were not captured.

---

## Exit criteria for Stage 2

1. `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` pass.
2. `npm run check:api-types` passes (generated types match `backend/openapi.json`).
3. No `any` without justification; no hardcoded risk thresholds; no secrets in `VITE_*`.
4. Every page uses real backend data; no mocked data in the production code path.
5. F11 integration checklist completed against the real backend.

## Deliverable: `docs/stage2-report.md`

What was built; page-by-page status (verified vs. not verified); exact commands; token-storage decision and trade-offs; any backend changes made; known limitations.
