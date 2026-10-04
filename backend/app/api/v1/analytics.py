"""Analytics API endpoints for executive dashboards and metrics."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import (
    ActivityTrendPoint,
    AnalyticsOverviewResponse,
    CustomerDistributionResponse,
    MonthlyChurnPoint,
    MonthlyRevenuePoint,
    SegmentationResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.segmentation_service import SegmentationService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get executive dashboard KPI overview",
)
def get_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AnalyticsOverviewResponse:
    """Calculates top-level KPI metrics across customers, revenue, churn, and models."""
    return AnalyticsService.get_overview(db=db)


@router.get(
    "/revenue",
    response_model=list[MonthlyRevenuePoint],
    summary="Get monthly revenue trend",
)
def get_revenue_trend(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[MonthlyRevenuePoint]:
    """Retrieves monthly billing revenue trends and average order values."""
    return AnalyticsService.get_revenue(db=db)


@router.get(
    "/churn",
    response_model=list[MonthlyChurnPoint],
    summary="Get monthly churn trend",
)
def get_churn_trend(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[MonthlyChurnPoint]:
    """Retrieves monthly cancellation volume and calculated churn rates."""
    return AnalyticsService.get_churn(db=db)


@router.get(
    "/customers",
    response_model=CustomerDistributionResponse,
    summary="Get customer demographic distribution",
)
def get_customer_distribution(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CustomerDistributionResponse:
    """Aggregates customer demographic breakdowns across channels, regions, and plans."""
    return AnalyticsService.get_customer_distribution(db=db)


@router.get(
    "/segments",
    response_model=SegmentationResponse,
    summary="Get RFM customer segmentation",
)
def get_segments(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SegmentationResponse:
    """Retrieves rule-based RFM customer segments and average monetary and recency values."""
    return SegmentationService.get_segments(db=db)


@router.get(
    "/activity",
    response_model=list[ActivityTrendPoint],
    summary="Get customer activity trends",
)
def get_activity_trend(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ActivityTrendPoint]:
    """Retrieves customer engagement volume and average session duration trends over time."""
    return AnalyticsService.get_activity(db=db)
