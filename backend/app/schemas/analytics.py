"""Analytics schemas for overview, revenue, churn, segmentation, and activity."""

from pydantic import BaseModel, ConfigDict


class ModelSummary(BaseModel):
    """Summary of an active machine learning model."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task: str
    algorithm: str
    version: str
    decision_threshold: float | None = None
    metrics_json: str


class ActiveModelsSummary(BaseModel):
    """Summary of currently active production models for churn and revenue."""

    churn: ModelSummary | None = None
    revenue: ModelSummary | None = None


class AnalyticsOverviewResponse(BaseModel):
    """High-level KPI metrics summary."""

    total_customers: int
    active_customers: int
    churned_customers: int
    churn_rate: float
    total_revenue_cents: int
    average_revenue_cents: float
    high_risk_count: int
    active_models: ActiveModelsSummary


class MonthlyRevenuePoint(BaseModel):
    """Monthly revenue aggregate data point."""

    period: str
    revenue_cents: int
    transaction_count: int
    average_order_value_cents: float


class MonthlyChurnPoint(BaseModel):
    """Monthly churn aggregate data point."""

    period: str
    churned_count: int
    active_count: int
    churn_rate: float


class CategoryCount(BaseModel):
    """Distribution bucket count and percentage."""

    category: str
    count: int
    percentage: float


class CustomerDistributionResponse(BaseModel):
    """Customer demographic and status breakdown."""

    total_customers: int
    by_status: list[CategoryCount]
    by_acquisition_channel: list[CategoryCount]
    by_region: list[CategoryCount]
    by_industry: list[CategoryCount]
    by_plan_tier: list[CategoryCount]


class SegmentSummary(BaseModel):
    """RFM segment summary metrics."""

    segment: str
    count: int
    percentage: float
    average_revenue_cents: float
    average_recency_days: float


class SegmentationResponse(BaseModel):
    """Rule-based RFM customer segmentation results."""

    total_customers: int
    summary: list[SegmentSummary]


class ActivityTrendPoint(BaseModel):
    """Customer activity trend data point."""

    period: str
    activity_type: str
    total_count: int
    avg_duration_seconds: float
