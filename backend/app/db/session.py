"""Database engine, session management, and connection configuration."""

from collections.abc import Generator
from typing import Any

import libsql
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import registry
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


class LibSQLDBAPIWrapper:
    """DBAPI 2.0 wrapper adapting the modern libsql package for SQLAlchemy."""

    def __init__(self, raw: Any) -> None:
        self.raw = raw
        self.paramstyle = raw.paramstyle
        self.Error = raw.Error

    def connect(self, *args: Any, **kwargs: Any) -> Any:
        if "check_same_thread" in kwargs:
            kwargs["_check_same_thread"] = kwargs.pop("check_same_thread")
        return self.raw.connect(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw, name)


class SQLiteDialect_libsql(SQLiteDialect_pysqlite):
    """Custom SQLAlchemy dialect for Turso libSQL driver."""

    driver = "libsql"
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls) -> Any:
        return LibSQLDBAPIWrapper(libsql)

    def on_connect(self) -> Any:
        def connect(conn: Any) -> None:
            # libsql does not support sqlite3 create_function()
            pass

        return connect


registry.register("sqlite.libsql", "app.db.session", "SQLiteDialect_libsql")


def build_engine(database_url: str | None = None) -> Engine:
    """Builds and returns a configured SQLAlchemy engine."""
    url = database_url or settings.DATABASE_URL

    connect_args: dict[str, Any] = {}
    if "sqlite" in url and "libsql" not in url:
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    # Ensure foreign keys are enforced on SQLite connections
    if "sqlite" in url:

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
