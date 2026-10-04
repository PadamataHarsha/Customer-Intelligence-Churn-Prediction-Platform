"""Analytics business logic service."""

from sqlalchemy.orm import Session

from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    ActiveModelsSummary,
    ActivityTrendPoint,
    AnalyticsOverviewResponse,
    CategoryCount,
    CustomerDistributionResponse,
    ModelSummary,
    MonthlyChurnPoint,
    MonthlyRevenuePoint,
)


class AnalyticsService:
    """Service providing aggregated dashboard metrics and trend analyses."""

    @staticmethod
    def get_overview(db: Session) -> AnalyticsOverviewResponse:
        """Computes top-level KPI metrics across customers, revenue, churn, and ML models."""
        counts = AnalyticsRepository.get_overview_counts(db)
        total_customers = counts["total_customers"]
        active_customers = counts["active_customers"]
        churned_customers = counts["churned_customers"]

        churn_rate = round(churned_customers / total_customers, 4) if total_customers > 0 else 0.0

        total_revenue_cents = AnalyticsRepository.get_total_revenue_cents(db)
        average_revenue_cents = (
            round(total_revenue_cents / total_customers, 2) if total_customers > 0 else 0.0
        )

        high_risk_count = AnalyticsRepository.get_high_risk_count(db)

        # Active ML models
        active_models_raw = AnalyticsRepository.get_active_models(db)
        churn_model = None
        revenue_model = None
        for m in active_models_raw:
            summary = ModelSummary(
                id=m["id"],
                name=m["name"],
                task=m["task"],
                algorithm=m["algorithm"],
                version=m["version"],
                decision_threshold=m.get("decision_threshold"),
                metrics_json=m["metrics_json"],
            )
            if m["task"] == "churn" and churn_model is None:
                churn_model = summary
            elif m["task"] == "revenue" and revenue_model is None:
                revenue_model = summary

        return AnalyticsOverviewResponse(
            total_customers=total_customers,
            active_customers=active_customers,
            churned_customers=churned_customers,
            churn_rate=churn_rate,
            total_revenue_cents=total_revenue_cents,
            average_revenue_cents=average_revenue_cents,
            high_risk_count=high_risk_count,
            active_models=ActiveModelsSummary(churn=churn_model, revenue=revenue_model),
        )

    @staticmethod
    def get_revenue(db: Session) -> list[MonthlyRevenuePoint]:
        """Retrieves monthly revenue time-series data."""
        data = AnalyticsRepository.get_revenue_trend(db)
        return [MonthlyRevenuePoint.model_validate(row) for row in data]

    @staticmethod
    def get_churn(db: Session) -> list[MonthlyChurnPoint]:
        """Retrieves monthly churn cancellations and rate trends."""
        data = AnalyticsRepository.get_churn_trend(db)
        return [MonthlyChurnPoint.model_validate(row) for row in data]

    @staticmethod
    def get_customer_distribution(db: Session) -> CustomerDistributionResponse:
        """Aggregates customer demographic breakdowns across channels, regions, and plans."""
        counts = AnalyticsRepository.get_overview_counts(db)
        total_customers = counts["total_customers"]

        def _to_category_counts(
            raw_rows: list[dict[str, int | str]], base_total: int
        ) -> list[CategoryCount]:
            res: list[CategoryCount] = []
            for r in raw_rows:
                cnt = int(r["count"])
                pct = round((cnt / base_total) * 100, 2) if base_total > 0 else 0.0
                res.append(CategoryCount(category=str(r["category"]), count=cnt, percentage=pct))
            return res

        by_status_raw = AnalyticsRepository.get_distribution_by_column(db, "customers", "status")
        by_channel_raw = AnalyticsRepository.get_distribution_by_column(
            db, "customer_profiles", "acquisition_channel"
        )
        by_region_raw = AnalyticsRepository.get_distribution_by_column(
            db, "customer_profiles", "region"
        )
        by_industry_raw = AnalyticsRepository.get_distribution_by_column(
            db, "customer_profiles", "industry"
        )
        by_tier_raw = AnalyticsRepository.get_distribution_by_plan_tier(db)

        return CustomerDistributionResponse(
            total_customers=total_customers,
            by_status=_to_category_counts(by_status_raw, total_customers),
            by_acquisition_channel=_to_category_counts(by_channel_raw, total_customers),
            by_region=_to_category_counts(by_region_raw, total_customers),
            by_industry=_to_category_counts(by_industry_raw, total_customers),
            by_plan_tier=_to_category_counts(by_tier_raw, counts["active_customers"]),
        )

    @staticmethod
    def get_activity(db: Session) -> list[ActivityTrendPoint]:
        """Retrieves customer activity volume and duration trends over time."""
        data = AnalyticsRepository.get_activity_trend(db)
        return [ActivityTrendPoint.model_validate(row) for row in data]
