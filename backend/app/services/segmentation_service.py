"""Rule-based RFM customer segmentation service."""

from sqlalchemy.orm import Session

from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import SegmentationResponse, SegmentSummary


class SegmentationService:
    """Service providing rule-based RFM segmentation analysis and assignments."""

    @staticmethod
    def get_segments(db: Session) -> SegmentationResponse:
        """Computes customer RFM segment counts and distributions."""
        raw_segments, total_customers = AnalyticsRepository.get_rfm_segments(db)

        summary: list[SegmentSummary] = []
        for r in raw_segments:
            cnt = int(r["count"])
            pct = round((cnt / total_customers) * 100, 2) if total_customers > 0 else 0.0
            summary.append(
                SegmentSummary(
                    segment=str(r["segment"]),
                    count=cnt,
                    percentage=pct,
                    average_revenue_cents=float(r["average_revenue_cents"]),
                    average_recency_days=float(r["average_recency_days"]),
                )
            )

        return SegmentationResponse(total_customers=total_customers, summary=summary)
