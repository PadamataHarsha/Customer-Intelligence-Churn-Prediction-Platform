# Customer Intelligence & Churn Prediction Platform

A production-quality SaaS-style analytics and predictive intelligence platform that helps businesses manage customer lifecycles, monitor subscriptions and revenue, perform rule-based RFM customer segmentation, **predict customer churn**, **predict near-term revenue**, compare ML models, and surface high-risk customers with actionable insights.

## Architecture

- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, scikit-learn
- **Database**: SQLite (local dev & testing) / Turso libSQL (production)
- **Frontend** (Stage 2): React, TypeScript (strict), Vite, Tailwind CSS, TanStack Query, Recharts
- **Deployment** (Stage 3): Docker, Railway, Vercel, GitHub Actions

For full system specifications, data definitions, and architectural rules, see [docs/project-brief.md](docs/project-brief.md).
