"""Synthetic dataset generator creating realistic customer lifecycle and behavioral data.

This module generates synthetic panels embedding realistic behavioral relationships:
- Churn probability increases with payment failures, support tickets, and inactivity.
- Churn probability decreases with engagement, product usage frequency, and tenure.
- Future revenue is correlated with active subscription plan tier and activity frequency.
- Injected stochastic noise ensures models learn generalized patterns without artificial perfection.

Documented explicitly as SYNTHETIC per Project Brief Section 6.
"""

import random
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd


def generate_synthetic_panel_dataset(
    num_customers: int = 200,
    num_snapshots: int = 12,
    seed: int = 42,
    base_date: datetime | None = None,
) -> pd.DataFrame:
    """Generates a synthetic panel dataset with ground-truth structural relationships and noise."""
    random.seed(seed)
    np.random.seed(seed)

    if base_date is None:
        base_date = datetime(2025, 1, 1)

    plans: list[dict[str, Any]] = [
        {"tier": "basic", "cycle": "monthly", "mrr": 2900.0},
        {"tier": "basic", "cycle": "annual", "mrr": 2416.0},
        {"tier": "pro", "cycle": "monthly", "mrr": 7900.0},
        {"tier": "pro", "cycle": "annual", "mrr": 6583.0},
        {"tier": "enterprise", "cycle": "monthly", "mrr": 29900.0},
        {"tier": "enterprise", "cycle": "annual", "mrr": 24916.0},
    ]

    channels = ["organic_search", "referral", "paid_ads", "outbound", "partner", "direct"]
    regions = ["north_america", "europe", "apac", "latin_america"]

    # Customer static demographic profiles
    customer_profiles: list[dict[str, Any]] = []
    for cid in range(1, num_customers + 1):
        chosen_plan = random.choice(plans)
        channel = random.choice(channels)
        region = random.choice(regions)
        creation_offset_days = random.randint(30, 700)
        created_at = base_date - timedelta(days=creation_offset_days)
        base_churn_tendency = float(np.random.beta(2, 5))
        customer_profiles.append(
            {
                "customer_id": cid,
                "created_at": created_at,
                "plan": chosen_plan,
                "channel": channel,
                "region": region,
                "base_churn_tendency": base_churn_tendency,
            }
        )

    rows: list[dict[str, Any]] = []

    # Generate monthly snapshots
    for s_idx in range(num_snapshots):
        snapshot_date = base_date + timedelta(days=s_idx * 30)

        for prof in customer_profiles:
            cid = int(prof["customer_id"])
            created_at = prof["created_at"]
            if created_at > snapshot_date:
                continue

            tenure_days = max(0, (snapshot_date - created_at).days)
            plan_dict: dict[str, Any] = prof["plan"]

            # Behavioral variables
            activity_30d = max(0, int(np.random.poisson(12) + np.random.normal(0, 3)))
            activity_90d = activity_30d + max(
                0, int(np.random.poisson(25) + np.random.normal(0, 5))
            )
            login_freq_30d = min(activity_30d, max(1, int(activity_30d * 0.4)))
            days_since_act = (
                max(0, int(np.random.exponential(5)))
                if activity_30d > 0
                else random.randint(15, 60)
            )

            support_tickets_90d = int(np.random.choice([0, 1, 2, 4], p=[0.70, 0.20, 0.08, 0.02]))
            payment_failures_90d = int(np.random.choice([0, 1, 2, 3], p=[0.85, 0.10, 0.03, 0.02]))

            # Engagement score
            act_pts = min(40.0, activity_30d * 2.0)
            login_pts = min(30.0, login_freq_30d * 5.0)
            rec_penalty = min(50.0, days_since_act * 1.5)
            engagement = max(0.0, min(100.0, round(30.0 + act_pts + login_pts - rec_penalty, 2)))

            mrr = float(plan_dict["mrr"])
            sub_length_days = min(tenure_days, random.randint(30, max(31, tenure_days)))
            txn_count_90d = 3 if plan_dict["cycle"] == "monthly" else 1
            avg_txn_val = mrr if plan_dict["cycle"] == "monthly" else mrr * 12.0
            total_rev = round(mrr * (tenure_days / 30.0), 2)

            # Structured Churn Probability Equation:
            # P(churn) rises with payment failures, tickets, dormancy; falls with engagement, tenure
            logit = (
                -2.2
                + 1.4 * payment_failures_90d
                + 0.8 * support_tickets_90d
                + 0.04 * days_since_act
                - 0.03 * engagement
                - 0.002 * tenure_days
                + (float(prof["base_churn_tendency"]) - 0.25) * 2.0
                + float(np.random.normal(0, 0.3))
            )
            churn_prob = 1.0 / (1.0 + np.exp(-logit))
            churned_30d = 1 if (np.random.rand() < churn_prob) else 0

            # Structured Future Revenue Equation:
            # Depends on plan, engagement, and whether customer churned in the window
            if churned_30d:
                future_rev = round(mrr * random.choice([0.0, 0.5, 1.0]), 2)
            else:
                noise_factor = float(np.random.normal(1.0, 0.08))
                future_rev = round(3.0 * mrr * noise_factor, 2)

            row: dict[str, Any] = {
                "customer_id": cid,
                "snapshot_date": snapshot_date.isoformat(),
                "tenure_days": tenure_days,
                "monthly_revenue": mrr,
                "total_revenue_to_date": total_rev,
                "transaction_count_90d": txn_count_90d,
                "avg_transaction_value_90d": avg_txn_val,
                "days_since_last_activity": days_since_act,
                "activity_count_30d": activity_30d,
                "activity_count_90d": activity_90d,
                "login_frequency_30d": login_freq_30d,
                "support_ticket_count_90d": support_tickets_90d,
                "payment_failure_count_90d": payment_failures_90d,
                "engagement_score": engagement,
                "subscription_length_days": sub_length_days,
                "plan_tier": plan_dict["tier"],
                "billing_cycle": plan_dict["cycle"],
                "acquisition_channel": prof["channel"],
                "region": prof["region"],
                "churned_30d": churned_30d,
                "future_revenue_90d": future_rev,
            }
            rows.append(row)

    return pd.DataFrame(rows)
