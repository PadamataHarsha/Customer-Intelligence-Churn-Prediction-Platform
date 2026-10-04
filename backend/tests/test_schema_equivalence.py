"""Test validating that database/schema.sql and Alembic migrations produce equivalent schemas."""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config


def test_schema_equivalence(tmp_path: Path) -> None:
    # 1. Setup paths
    root_dir = Path(__file__).resolve().parent.parent.parent
    schema_sql_path = root_dir / "database" / "schema.sql"
    alembic_ini_path = root_dir / "backend" / "alembic.ini"

    assert schema_sql_path.exists(), f"schema.sql not found at {schema_sql_path}"
    assert alembic_ini_path.exists(), f"alembic.ini not found at {alembic_ini_path}"

    # 2. Build DB from schema.sql
    db_schema_file = tmp_path / "schema_from_sql.db"
    conn_sql = sqlite3.connect(db_schema_file)
    with open(schema_sql_path, encoding="utf-8") as f:
        sql_content = f.read()
    conn_sql.executescript(sql_content)
    conn_sql.close()

    # 3. Build DB from Alembic migrations
    db_alembic_file = tmp_path / "schema_from_alembic.db"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_alembic_file}")
    command.upgrade(alembic_cfg, "head")

    # 4. Inspect both databases
    engine_sql = create_engine(f"sqlite:///{db_schema_file}")
    engine_alembic = create_engine(f"sqlite:///{db_alembic_file}")

    inspector_sql = inspect(engine_sql)
    inspector_alembic = inspect(engine_alembic)

    tables_sql = set(inspector_sql.get_table_names())
    tables_alembic = set(inspector_alembic.get_table_names())

    # Filter out alembic's internal version table and sqlite internal tables
    tables_alembic.discard("alembic_version")
    tables_sql = {t for t in tables_sql if not t.startswith("sqlite_")}
    tables_alembic = {t for t in tables_alembic if not t.startswith("sqlite_")}

    # Assert same tables exist
    assert tables_sql == tables_alembic, f"Table mismatch: {tables_sql ^ tables_alembic}"

    expected_tables = {
        "roles",
        "users",
        "customers",
        "customer_profiles",
        "plans",
        "subscriptions",
        "transactions",
        "customer_activity",
        "customer_events",
        "customer_segments",
        "ml_models",
        "predictions",
        "model_training_runs",
        "model_artifacts",
        "audit_logs",
    }
    assert expected_tables.issubset(tables_sql), (
        f"Missing expected tables: {expected_tables - tables_sql}"
    )

    # Assert column definitions, nullability, PKs, and FKs match
    for table_name in expected_tables:
        cols_sql = {col["name"]: col for col in inspector_sql.get_columns(table_name)}
        cols_alembic = {col["name"]: col for col in inspector_alembic.get_columns(table_name)}

        assert set(cols_sql.keys()) == set(cols_alembic.keys()), (
            f"Column mismatch in {table_name}: {set(cols_sql.keys()) ^ set(cols_alembic.keys())}"
        )

        for col_name, c_sql in cols_sql.items():
            c_alembic = cols_alembic[col_name]
            msg = (
                f"Nullable mismatch in {table_name}.{col_name}: "
                f"sql={c_sql['nullable']}, alembic={c_alembic['nullable']}"
            )
            assert c_sql["nullable"] == c_alembic["nullable"], msg

        # Check Primary Keys
        pk_sql = inspector_sql.get_pk_constraint(table_name)["constrained_columns"]
        pk_alembic = inspector_alembic.get_pk_constraint(table_name)["constrained_columns"]
        assert pk_sql == pk_alembic, f"PK mismatch in {table_name}: {pk_sql} != {pk_alembic}"

        # Check Foreign Keys
        fks_sql = {
            (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
            for fk in inspector_sql.get_foreign_keys(table_name)
        }
        fks_alembic = {
            (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
            for fk in inspector_alembic.get_foreign_keys(table_name)
        }
        assert fks_sql == fks_alembic, (
            f"FK mismatch in {table_name}: SQL={fks_sql} vs Alembic={fks_alembic}"
        )

    engine_sql.dispose()
    engine_alembic.dispose()
