# How to Use These Prompts

This pack replaces the single mega-prompt with **one shared brief + three staged prompts**. Each stage ends in a verified, committed state, so a failure in one stage never corrupts the rest.

| File | What it is | When to use |
|---|---|---|
| `01-project-brief.md` | Shared source of truth: architecture, data definitions, API surface, rules | Copy into the repo as `docs/project-brief.md` **before** Stage 1 |
| `02-stage1-backend-database-ml.md` | Database, backend, auth, analytics, synthetic data, ML | Paste into Antigravity first |
| `03-stage2-frontend.md` | React/TypeScript frontend wired to the real backend | Paste after Stage 1 is committed |
| `04-stage3-deploy-docs.md` | Docker, CI/CD, Railway, Vercel, docs, final security review | Paste after Stage 2 is committed |

## Workflow

1. Create an empty folder `customer-intelligence-platform/` and run `git init`.
2. Create `docs/` and copy `01-project-brief.md` into it as `docs/project-brief.md`.
3. Open the folder in Antigravity. Use its **planning mode** if available, so you can review the implementation plan before code is written.
4. Paste the contents of `02-stage1-...md`. Review the plan, approve, and let it run.
5. When Stage 1 finishes, read `docs/stage1-report.md`, spot-check it yourself (run the commands in the report), then `git commit` / tag `stage-1`.
6. Repeat for Stage 2, then Stage 3.

## What you must do manually (an agent cannot do these for you)

- Create a **Turso** account and database, and generate an auth token (Stage 3 docs walk through the commands).
- Create the **Railway** project and the **Vercel** project and connect your GitHub repo.
- Put real secrets only in Railway/Vercel/Turso environment settings or a local `.env` that is git-ignored. Never paste them into a prompt or commit them.

## Changes from the original mega-prompt

- **Staged execution** instead of one 66-section run.
- **Contradictory last line removed** (the original asked for a prompt, then said "now build").
- **Model artifacts survive Railway redeploys**: the production artifact store is database-backed (BLOBs in Turso); local disk is dev/test only.
- **Turso/SQLAlchemy compatibility is verified in a spike first**, with defined fallbacks, instead of assumed.
- **Leakage-proof data definitions**: explicit snapshot dates, label windows, and revenue target.
- **Contract-first is mandatory**: TypeScript types are generated from OpenAPI, and CI fails on drift.
- **Registration cannot self-create admins**; seed data ships with no usable credentials.
- **Exact versions pinned** via lockfiles after checking current stable releases.
