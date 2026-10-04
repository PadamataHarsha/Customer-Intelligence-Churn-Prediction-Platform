"""Main FastAPI application factory and entry point."""

from typing import Any

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import limiter
from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.plans import router as plans_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import get_db


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    setup_logging(settings.LOG_LEVEL)

    application = FastAPI(
        title="Customer Intelligence & Churn Prediction API",
        description=(
            "Production-quality SaaS platform for customer lifecycle analytics, "
            "churn prediction, near-term revenue forecasting, and ML model management."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. State attachments (e.g. rate limiter)
    application.state.limiter = limiter

    # 2. Exception handlers
    register_exception_handlers(application)

    # 3. CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Custom Request Middleware (Request ID, Logging, Security Headers)
    application.add_middleware(RequestContextMiddleware)

    # 5. Ops Routes
    @application.get("/health", tags=["Ops"], summary="Process liveness probe")
    def health_check() -> dict[str, str]:
        """Simple liveness check returning process status."""
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    @application.get("/ready", tags=["Ops"], summary="System readiness probe")
    def readiness_check(db: Session = Depends(get_db)) -> Any:
        """Readiness check validating database connectivity without exposing internals."""
        try:
            db.execute(text("SELECT 1;"))
            return {"status": "ready"}
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "error": "Database unavailable"},
            )

    # 6. API v1 Routers
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(users_router, prefix="/api/v1")
    application.include_router(customers_router, prefix="/api/v1")
    application.include_router(plans_router, prefix="/api/v1")
    application.include_router(subscriptions_router, prefix="/api/v1")
    application.include_router(transactions_router, prefix="/api/v1")

    return application


app = create_app()
