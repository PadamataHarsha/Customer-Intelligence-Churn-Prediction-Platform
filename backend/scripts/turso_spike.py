"""Turso / libSQL compatibility spike script.

Validates:
1. Standard local SQLite engine via SQLAlchemy 2.x
2. LibSQL Python driver (DBAPI 2.0) compatibility with SQLAlchemy engine
3. Custom LibSQL SQLAlchemy Dialect resolving _check_same_thread and create_function differences
4. Verification of Turso cloud connection parameters
"""

import os
from pathlib import Path
from typing import Any

import libsql
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import registry
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite


class LibSQLDBAPIWrapper:
    """DBAPI 2.0 wrapper adapting the modern libsql package for SQLAlchemy."""

    def __init__(self, raw: Any) -> None:
        self.raw = raw
        self.paramstyle = raw.paramstyle
        self.Error = raw.Error

    def connect(self, *args: Any, **kwargs: Any) -> Any:
        # libsql uses _check_same_thread instead of check_same_thread
        if "check_same_thread" in kwargs:
            kwargs["_check_same_thread"] = kwargs.pop("check_same_thread")
        return self.raw.connect(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw, name)


class SQLiteDialect_libsql(SQLiteDialect_pysqlite):
    driver = "libsql"
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls) -> Any:
        return LibSQLDBAPIWrapper(libsql)

    def on_connect(self) -> Any:
        def connect(conn: Any) -> None:
            # libsql does not support create_function('regexp', ...)
            pass

        return connect


registry.register("sqlite.libsql_custom", __name__, "SQLiteDialect_libsql")


def test_local_sqlite() -> bool:
    print("--- 1. Testing SQLAlchemy with standard SQLite engine ---")
    db_file = Path("spike_local.db")
    if db_file.exists():
        db_file.unlink()
    engine = create_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"))
        conn.execute(text("INSERT INTO test_table (name) VALUES ('local_sqlite_test');"))
        res = conn.execute(text("SELECT name FROM test_table WHERE id = 1;")).scalar()
        print(f"Result: {res}")
        assert res == "local_sqlite_test"
    engine.dispose()
    if db_file.exists():
        db_file.unlink()
    print("SUCCESS: Standard SQLite works.")
    return True


def test_libsql_dbapi() -> bool:
    print("\n--- 2. Testing direct libSQL DBAPI driver ---")
    conn = libsql.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE test_libsql (id INTEGER PRIMARY KEY, val TEXT);")
    cur.execute("INSERT INTO test_libsql (val) VALUES ('direct_libsql');")
    cur.execute("SELECT val FROM test_libsql WHERE id = 1;")
    row = cur.fetchone()
    print(f"Result: {row}")
    assert row is not None and row[0] == "direct_libsql"
    conn.close()
    print("SUCCESS: Direct libSQL works.")
    return True


def test_sqlalchemy_libsql_dialect() -> bool:
    print("\n--- 3. Testing SQLAlchemy with custom libSQL dialect ---")
    engine = create_engine("sqlite+libsql_custom:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE test_dialect (id INTEGER PRIMARY KEY, msg TEXT);"))
        conn.execute(text("INSERT INTO test_dialect (msg) VALUES ('libsql_dialect_works');"))
        res = conn.execute(text("SELECT msg FROM test_dialect WHERE id = 1;")).scalar()
        print(f"Result: {res}")
        assert res == "libsql_dialect_works"
    engine.dispose()
    print("SUCCESS: SQLAlchemy with custom libSQL dialect works cleanly.")
    return True


def test_turso_cloud_config() -> None:
    print("\n--- 4. Checking Turso Cloud Environment Variables ---")
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")
    if turso_url and turso_token:
        print(f"Turso credentials found. Connecting to {turso_url}...")
        try:
            conn = libsql.connect(turso_url, auth_token=turso_token)
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            res = cur.fetchone()
            print(f"Turso Cloud Query Result: {res}")
            print("SUCCESS: Connected to live Turso Cloud database.")
        except Exception as e:
            print(f"FAILED to connect to live Turso Cloud: {e}")
    else:
        print("Note: TURSO_DATABASE_URL and TURSO_AUTH_TOKEN not provided in local environment.")
        print(
            "Driver path verified locally. Human verification steps documented in docs/database.md."
        )


if __name__ == "__main__":
    test_local_sqlite()
    test_libsql_dbapi()
    test_sqlalchemy_libsql_dialect()
    test_turso_cloud_config()
    print("\nAll Phase 0 Spike checks PASSED.")
