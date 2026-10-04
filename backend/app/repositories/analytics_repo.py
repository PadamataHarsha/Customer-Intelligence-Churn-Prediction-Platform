"""Pure SQL aggregations repository for analytics and metrics."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class AnalyticsRepository:
    """Repository executing pure SQL queries for analytical endpoints without N+1."""

    @staticmethod
    def get_overview_counts(db: Session) -> dict[str, int]:
        """Calculates customer counts by status in a single query."""
        stmt = text("""
            SELECT
                COUNT(*) as total_customers,
                COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0)
                    as active_customers,
                COALESCE(SUM(CASE WHEN status = 'churned' THEN 1 ELSE 0 END), 0)
                    as churned_customers
            FROM customers;
        """)
        row = db.execute(stmt).mappings().one()
        return {
            "total_customers": int(row["total_customers"]),
            "active_customers": int(row["active_customers"]),
            "churned_customers": int(row["churned_customers"]),
        }

    @staticmethod
    def get_total_revenue_cents(db: Session) -> int:
        """Sums all settled payment transactions."""
        stmt = text("""
            SELECT COALESCE(SUM(amount_cents), 0) as total_rev
            FROM transactions
            WHERE status = 'succeeded' AND type = 'payment';
        """)
        result = db.execute(stmt).scalar()
        return int(result or 0)

    @staticmethod
    def get_high_risk_count(db: Session) -> int:
        """Counts customers whose latest prediction is classified as high-risk."""
        stmt = text("""
            WITH latest_preds AS (
                SELECT customer_id, risk_category,
                       ROW_NUMBER() OVER (
                           PARTITION BY customer_id ORDER BY created_at DESC
                       ) as rn
                FROM predictions
            )
            SELECT COUNT(*) FROM latest_preds WHERE rn = 1 AND risk_category = 'high';
        """)
        result = db.execute(stmt).scalar()
        return int(result or 0)

    @staticmethod
    def get_active_models(db: Session) -> list[dict[str, Any]]:
        """Retrieves active models for both churn and revenue tasks."""
        stmt = text("""
            SELECT id, name, task, algorithm, version, decision_threshold, metrics_json
            FROM ml_models
            WHERE status = 'active';
        """)
        return [dict(row) for row in db.execute(stmt).mappings().all()]

    @staticmethod
    def get_revenue_trend(db: Session) -> list[dict[str, Any]]:
        """Calculates monthly revenue trends."""
        stmt = text("""
            SELECT
                strftime('%Y-%m', transaction_date) as period,
                COALESCE(SUM(amount_cents), 0) as revenue_cents,
                COUNT(*) as transaction_count,
                COALESCE(ROUND(AVG(amount_cents), 2), 0.0) as average_order_value_cents
            FROM transactions
            WHERE status = 'succeeded' AND type = 'payment'
            GROUP BY strftime('%Y-%m', transaction_date)
            ORDER BY period ASC;
        """)
        return [dict(row) for row in db.execute(stmt).mappings().all()]

    @staticmethod
    def get_churn_trend(db: Session) -> list[dict[str, Any]]:
        """Calculates monthly churn cancellations and churn rate."""
        stmt = text("""
            WITH cancellations AS (
                SELECT
                    strftime('%Y-%m', cancelled_at) as period,
                    COUNT(*) as churned_count
                FROM subscriptions
                WHERE cancelled_at IS NOT NULL
                GROUP BY strftime('%Y-%m', cancelled_at)
            ),
            active_monthly AS (
                SELECT
                    strftime('%Y-%m', current_period_start) as period,
                    COUNT(DISTINCT customer_id) as active_count
                FROM subscriptions
                WHERE status = 'active'
                GROUP BY strftime('%Y-%m', current_period_start)
            )
            SELECT
                c.period,
                c.churned_count,
                COALESCE(a.active_count, 0) as active_count,
                COALESCE(
                    ROUND(
                        CAST(c.churned_count AS REAL)
                        / NULLIF(c.churned_count + COALESCE(a.active_count, 0), 0),
                        4
                    ),
                    0.0
                ) as churn_rate
            FROM cancellations c
            LEFT JOIN active_monthly a ON c.period = a.period
            ORDER BY c.period ASC;
        """)
        return [dict(row) for row in db.execute(stmt).mappings().all()]

    @staticmethod
    def get_distribution_by_column(db: Session, table: str, column: str) -> list[dict[str, Any]]:
        """Generic aggregation helper for customer demographic distribution."""
        stmt = text(f"""
            SELECT
                COALESCE(NULLIF({column}, ''), 'unknown') as category,
                COUNT(*) as count
            FROM {table}
            GROUP BY category
            ORDER BY count DESC;
        """)
        return [dict(row) for row in db.execute(stmt).mappings().all()]

    @staticmethod
    def get_distribution_by_plan_tier(db: Session) -> list[dict[str, Any]]:
        """Calculates active subscription counts grouped by plan tier."""
        stmt = text("""
            SELECT
                COALESCE(p.tier, 'unknown') as category,
                COUNT(DISTINCT s.customer_id) as count
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.status = 'active'
            GROUP BY p.tier
            ORDER BY count DESC;
        """)
        return [dict(row) for row in db.execute(stmt).mappings().all()]

    @staticmethod
    def get_rfm_segments(db: Session) -> tuple[list[dict[str, Any]], int]:
        """Calculates rule-based RFM customer segmentation in pure SQL."""
        cust_count_stmt = text("SELECT COUNT(*) FROM customers;")
        total_customers = db.execute(cust_count_stmt).scalar() or 0
        if total_customers == 0:
            return [], 0

        ref_date_stmt = text(
            "SELECT COALESCE(MAX(timestamp), CURRENT_TIMESTAMP) FROM customer_activity;"
        )
        ref_date = db.execute(ref_date_stmt).scalar()

        rfm_stmt = text(f"""
            WITH act_stats AS (
                SELECT
                    customer_id,
                    MAX(timestamp) AS last_act,
                    COUNT(id) AS frequency
                FROM customer_activity
                GROUP BY customer_id
            ),
            txn_stats AS (
                SELECT
                    customer_id,
                    SUM(amount_cents) AS monetary_cents
                FROM transactions
                WHERE status = 'succeeded' AND type = 'payment'
                GROUP BY customer_id
            ),
            customer_rfm AS (
                SELECT
                    c.id AS customer_id,
                    c.status,
                    c.created_at,
                    CAST(
                        (julianday('{ref_date}')
                         - julianday(COALESCE(a.last_act, c.created_at)))
                        AS INTEGER
                    ) AS recency_days,
                    COALESCE(a.frequency, 0) AS frequency,
                    COALESCE(t.monetary_cents, 0) AS monetary_cents
                FROM customers c
                LEFT JOIN act_stats a ON c.id = a.customer_id
                LEFT JOIN txn_stats t ON c.id = t.customer_id
            ),
            classified AS (
                SELECT
                    customer_id,
                    status,
                    recency_days,
                    frequency,
                    monetary_cents,
                    CASE
                        WHEN status = 'churned' OR recency_days > 90 THEN 'Dormant'
                        WHEN recency_days <= 30
                             AND monetary_cents >= 150000
                             AND frequency >= 10 THEN 'Champions'
                        WHEN recency_days <= 45 AND frequency >= 5 THEN 'Loyal'
                        WHEN CAST(
                            (julianday('{ref_date}') - julianday(created_at)) AS INTEGER
                        ) <= 60 THEN 'New'
                        ELSE 'At Risk'
                    END AS segment_name
                FROM customer_rfm
            )
            SELECT
                segment_name as segment,
                COUNT(*) as count,
                COALESCE(ROUND(AVG(monetary_cents), 2), 0.0) as average_revenue_cents,
                COALESCE(ROUND(AVG(recency_days), 2), 0.0) as average_recency_days
            FROM classified
            GROUP BY segment_name
            ORDER BY count DESC;
        """)
        rows = [dict(r) for r in db.execute(rfm_stmt).mappings().all()]
        return rows, total_customers

    @staticmethod
    def get_activity_trend(db: Session) -> list[dict[str, Any]]:
        """Calculates monthly activity trends grouped by activity type."""
        stmt = text("""
            SELECT
                strftime('%Y-%m', timestamp) AS period,
                activity_type,
                COALESCE(SUM(activity_count), 0) AS total_count,
                COALESCE(ROUND(AVG(duration_seconds), 2), 0.0) as avg_duration_seconds
            FROM customer_activity
            GROUP BY strftime('%Y-%m', timestamp), activity_type
            ORDER BY period ASC, activity_type ASC;
        """)
        return [dict(row) for row in db.execute(stmt).mappings().all()]
