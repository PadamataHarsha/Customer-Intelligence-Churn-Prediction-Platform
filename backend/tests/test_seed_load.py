"""Test verifying that database/seed.sql loads cleanly into a database created from schema.sql."""

import sqlite3
from pathlib import Path


def test_seed_load_and_foreign_keys(tmp_path: Path) -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    schema_sql_path = root_dir / "database" / "schema.sql"
    seed_sql_path = root_dir / "database" / "seed.sql"

    db_file = tmp_path / "test_seed.db"
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON;")

    # 1. Load schema
    with open(schema_sql_path, encoding="utf-8") as f:
        conn.executescript(f.read())

    # 2. Load seed
    with open(seed_sql_path, encoding="utf-8") as f:
        conn.executescript(f.read())

    # 3. Check foreign keys
    fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(fk_errors) == 0, f"Foreign key check failed: {fk_errors}"

    # 4. Verify entities populated
    customer_count = conn.execute("SELECT COUNT(*) FROM customers;").fetchone()[0]
    assert customer_count == 200, f"Expected 200 customers, got {customer_count}"

    profile_count = conn.execute("SELECT COUNT(*) FROM customer_profiles;").fetchone()[0]
    assert profile_count == 200

    plan_count = conn.execute("SELECT COUNT(*) FROM plans;").fetchone()[0]
    assert plan_count == 6

    # 5. Verify security constraint: NO seeded users with credentials
    user_count = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
    assert user_count == 0, "Seed data must not contain user credentials"

    # 6. Verify role records exist
    role_count = conn.execute("SELECT COUNT(*) FROM roles;").fetchone()[0]
    assert role_count == 3

    conn.close()
