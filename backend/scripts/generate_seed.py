"""Deterministic synthetic seed data generator for the Customer Intelligence Platform.

Generates database/seed.sql containing:
- 3 Roles (admin, analyst, viewer) - NO user credentials
- 6 Standard Subscription Plans (Basic, Pro, Enterprise x Monthly, Annual)
- ~200 Customers with complete profiles (channels, regions, industries)
- 12-24 months of subscriptions, billing transactions, activity logs, and events
- RFM customer segments
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_seed_data(output_path: Path, seed: int = 42) -> None:
    random.seed(seed)
    base_date = datetime(2026, 1, 1, 0, 0, 0)

    lines: list[str] = [
        "-- Synthetic Seed Data for Customer Intelligence Platform",
        "-- Deterministically generated with seed = 42",
        "-- Zero user credentials included; use CLI create-admin to establish accounts",
        "PRAGMA foreign_keys = ON;\n",
    ]

    # 1. Roles
    lines.append("-- Roles")
    lines.append(
        "INSERT OR IGNORE INTO roles (id, name, description) VALUES "
        "(1, 'admin', 'Administrator with full system privileges'), "
        "(2, 'analyst', 'Analyst with customer and ML experimentation privileges'), "
        "(3, 'viewer', 'Read-only viewer');\n"
    )

    # 2. Plans
    lines.append("-- Plans")
    plans = [
        (1, "Basic Monthly", "plan_basic_m", "basic", "monthly", 2900, "USD", 1),
        (2, "Basic Annual", "plan_basic_y", "basic", "annual", 29000, "USD", 1),
        (3, "Pro Monthly", "plan_pro_m", "pro", "monthly", 7900, "USD", 1),
        (4, "Pro Annual", "plan_pro_y", "pro", "annual", 79000, "USD", 1),
        (5, "Enterprise Monthly", "plan_ent_m", "enterprise", "monthly", 29900, "USD", 1),
        (6, "Enterprise Annual", "plan_ent_y", "enterprise", "annual", 299000, "USD", 1),
    ]
    for p in plans:
        stmt = (
            "INSERT OR IGNORE INTO plans "
            "(id, name, code, tier, billing_cycle, price_cents, currency, is_active) VALUES "
            f"({p[0]}, '{p[1]}', '{p[2]}', '{p[3]}', '{p[4]}', {p[5]}, '{p[6]}', {p[7]});"
        )
        lines.append(stmt)
    lines.append("")

    # 3. Customers and Profiles
    first_names = [
        "Alex",
        "Jordan",
        "Taylor",
        "Morgan",
        "Sam",
        "Chris",
        "Pat",
        "Riley",
        "Casey",
        "Avery",
        "Jamie",
        "Cameron",
        "Dakota",
        "Reese",
        "Quinn",
        "Skyler",
        "Rowan",
        "Hayden",
        "Logan",
        "Emerson",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Miller",
        "Davis",
        "Wilson",
        "Anderson",
        "Taylor",
        "Thomas",
        "Moore",
        "Jackson",
        "Martin",
        "Lee",
        "Perez",
        "Thompson",
        "White",
        "Harris",
        "Sanchez",
    ]
    company_prefixes = [
        "Apex",
        "Vertex",
        "Nova",
        "Pulse",
        "Nexus",
        "Zenith",
        "Cloud",
        "Data",
        "Alpha",
        "Omni",
        "Hyper",
        "Synapse",
        "Quantum",
        "Echo",
        "Aura",
        "Prime",
        "Vanguard",
        "Catalyst",
        "Starlight",
        "Core",
    ]
    company_suffixes = [
        "Tech",
        "Labs",
        "Solutions",
        "Analytics",
        "Systems",
        "AI",
        "Cloud",
        "Dynamics",
        "Group",
        "Works",
    ]

    channels = ["organic_search", "paid_ads", "referral", "sales", "outbound"]
    regions = ["north_america", "europe", "asia_pacific", "latin_america"]
    industries = ["saas", "fintech", "healthcare", "ecommerce", "logistics"]
    company_sizes = ["1-10", "11-50", "51-200", "201-1000", "1000+"]

    num_customers = 200
    sub_id_counter = 1
    txn_id_counter = 1
    act_id_counter = 1
    evt_id_counter = 1

    lines.append("-- Customers, Profiles, Subscriptions, Transactions, Activity & Events")

    for cust_id in range(1, num_customers + 1):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{cust_id}@example.com"
        company = f"{random.choice(company_prefixes)} {random.choice(company_suffixes)}"
        phone = f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}"
        ext_id = f"cust_{cust_id:04d}"

        # Join date: between 300 and 700 days before base_date
        join_days_ago = random.randint(300, 720)
        created_at = base_date - timedelta(days=join_days_ago)
        created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")

        # Determine churn intent: ~22% baseline churn probability influenced by channel/plan
        is_churned = random.random() < 0.22
        status = "churned" if is_churned else "active"

        cust_sql = (
            "INSERT INTO customers "
            "(id, external_id, name, email, phone, company, status, created_at, updated_at) "
            f"VALUES ({cust_id}, '{ext_id}', '{name}', '{email}', '{phone}', "
            f"'{company}', '{status}', '{created_str}', '{created_str}');"
        )
        lines.append(cust_sql)

        # Profile
        ch = random.choice(channels)
        reg = random.choice(regions)
        ind = random.choice(industries)
        cs = random.choice(company_sizes)
        meta = json.dumps({"lead_score": random.randint(30, 99), "onboarded": True})
        prof_sql = (
            "INSERT INTO customer_profiles "
            "(customer_id, acquisition_channel, region, industry, "
            "company_size, metadata_json, created_at, updated_at) "
            f"VALUES ({cust_id}, '{ch}', '{reg}', '{ind}', '{cs}', "
            f"'{meta}', '{created_str}', '{created_str}');"
        )
        lines.append(prof_sql)

        # Plan selection
        plan = random.choice(plans)
        plan_id = plan[0]
        plan_cycle = plan[4]
        plan_price = plan[5]

        # Subscription lifetime
        if is_churned:
            sub_duration_days = random.randint(60, max(61, join_days_ago - 30))
            sub_end = created_at + timedelta(days=sub_duration_days)
            cancelled_at_str = f"'{sub_end.strftime('%Y-%m-%d %H:%M:%S')}'"
            sub_status = "cancelled"
        else:
            sub_end = base_date + timedelta(days=365 if plan_cycle == "annual" else 30)
            cancelled_at_str = "NULL"
            sub_status = "active"

        sub_start_str = created_str
        sub_end_str = sub_end.strftime("%Y-%m-%d %H:%M:%S")

        current_sub_id = sub_id_counter
        sub_id_counter += 1
        sub_sql = (
            "INSERT INTO subscriptions "
            "(id, customer_id, plan_id, status, current_period_start, "
            "current_period_end, cancelled_at, created_at, updated_at) "
            f"VALUES ({current_sub_id}, {cust_id}, {plan_id}, '{sub_status}', "
            f"'{sub_start_str}', '{sub_end_str}', {cancelled_at_str}, "
            f"'{created_str}', '{created_str}');"
        )
        lines.append(sub_sql)

        # Transactions
        cycle_days = 365 if plan_cycle == "annual" else 30
        curr_tx_date = created_at
        active_end = sub_end if is_churned else base_date

        while curr_tx_date <= active_end:
            tx_status = "succeeded"
            if is_churned and curr_tx_date > (active_end - timedelta(days=cycle_days)):
                # Higher rate of failed payment right before churn
                if random.random() < 0.6:
                    tx_status = "failed"
            else:
                if random.random() < 0.04:
                    tx_status = "failed"

            tx_date_str = curr_tx_date.strftime("%Y-%m-%d %H:%M:%S")
            tx_sql = (
                "INSERT INTO transactions "
                "(id, customer_id, subscription_id, amount_cents, currency, "
                "status, type, transaction_date, created_at) "
                f"VALUES ({txn_id_counter}, {cust_id}, {current_sub_id}, "
                f"{plan_price}, 'USD', '{tx_status}', 'payment', "
                f"'{tx_date_str}', '{tx_date_str}');"
            )
            lines.append(tx_sql)
            txn_id_counter += 1
            curr_tx_date += timedelta(days=cycle_days)

        # Customer Activity (sessions)
        num_sessions = random.randint(15, 60) if not is_churned else random.randint(5, 25)
        for _ in range(num_sessions):
            if is_churned:
                # Activity clustered earlier in customer lifecycle
                act_day_offset = random.randint(0, max(1, sub_duration_days - 20))
            else:
                act_day_offset = random.randint(0, join_days_ago)

            act_time = created_at + timedelta(days=act_day_offset, hours=random.randint(8, 20))
            act_str = act_time.strftime("%Y-%m-%d %H:%M:%S")
            act_type = random.choice(
                ["dashboard_view", "report_export", "api_call", "feature_usage"]
            )
            dur = random.randint(60, 3600)
            act_sql = (
                "INSERT INTO customer_activity "
                "(id, customer_id, session_id, activity_type, activity_count, "
                "duration_seconds, timestamp, created_at) "
                f"VALUES ({act_id_counter}, {cust_id}, 'sess_{act_id_counter:06d}', "
                f"'{act_type}', {random.randint(1, 5)}, {dur}, '{act_str}', '{act_str}');"
            )
            lines.append(act_sql)
            act_id_counter += 1

        # Customer Events (support tickets, payment warnings)
        num_events = random.randint(1, 4) if not is_churned else random.randint(3, 9)
        for _ in range(num_events):
            evt_offset = random.randint(0, min(join_days_ago, 300))
            evt_time = created_at + timedelta(days=evt_offset)
            evt_str = evt_time.strftime("%Y-%m-%d %H:%M:%S")
            if is_churned:
                evt_type = random.choice(
                    [
                        "support_ticket_high",
                        "payment_failed_alert",
                        "feature_dissatisfaction",
                        "cancellation_inquiry",
                    ]
                )
                sev = "warning" if "alert" in evt_type else "error"
            else:
                evt_type = random.choice(
                    [
                        "support_ticket_routine",
                        "plan_inquiry",
                        "onboarding_completed",
                        "api_token_created",
                    ]
                )
                sev = "info"

            evt_detail = json.dumps({"note": f"Automated log for event {evt_type}"})
            evt_sql = (
                "INSERT INTO customer_events "
                "(id, customer_id, event_type, severity, details_json, timestamp, created_at) "
                f"VALUES ({evt_id_counter}, {cust_id}, '{evt_type}', '{sev}', "
                f"'{evt_detail}', '{evt_str}', '{evt_str}');"
            )
            lines.append(evt_sql)
            evt_id_counter += 1

        # Customer Segment (RFM rule-based)
        if is_churned:
            segment_name = "Dormant"
            rfm = {"r": 1, "f": 2, "m": 2}
        elif join_days_ago < 350:
            segment_name = "New"
            rfm = {"r": 5, "f": 3, "m": 3}
        elif plan_price >= 7900:
            segment_name = random.choice(["Champions", "Loyal"])
            rfm = {"r": 5, "f": 5, "m": 5}
        else:
            segment_name = random.choice(["Loyal", "At Risk"])
            rfm = {"r": 3, "f": 3, "m": 3}

        assigned_str = base_date.strftime("%Y-%m-%d %H:%M:%S")
        seg_sql = (
            "INSERT INTO customer_segments "
            "(id, customer_id, segment_name, rfm_score_json, assigned_at, created_at) "
            f"VALUES ({cust_id}, {cust_id}, '{segment_name}', "
            f"'{json.dumps(rfm)}', '{assigned_str}', '{assigned_str}');"
        )
        lines.append(seg_sql)

    lines.append("\n-- End of seed data")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Generated {len(lines)} lines of seed SQL into {output_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent.parent / "database" / "seed.sql"
    generate_seed_data(out)
