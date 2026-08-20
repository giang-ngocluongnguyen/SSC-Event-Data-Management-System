import json
from collections.abc import Mapping
from contextlib import contextmanager

import streamlit as st
from sqlalchemy import URL, create_engine, text


MASTER_TABLES = ["events", "locations", "event_types", "participants", "partners"]
TRANSACTION_TABLES = ["event_registration", "event_registered_attendee"]

AUDITED_TABLES = {
    "events": ["event_id"],
    "locations": ["location_id"],
    "event_types": ["etype_id"],
    "participants": ["participant_id"],
    "partners": ["partner_id"],
    "event_registration": ["registration_id"],
    "event_registered_attendee": ["registration_id", "participant_id"],
}

SCHEMA = "public"
REQUIRED_TABLES = set(MASTER_TABLES + TRANSACTION_TABLES + ["audit_log"])


@st.cache_resource
def get_engine():
    """Create one reusable SQLAlchemy engine for Supabase PostgreSQL."""
    config = st.secrets["database"]
    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=int(config.get("port", 5432)),
        database=config.get("database", "postgres"),
    )
    return create_engine(
        database_url,
        connect_args={"sslmode": config.get("sslmode", "require")},
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=2,
    )


def _prepare_statement(sql, params=()):
    """Convert positional placeholders into SQLAlchemy bind parameters."""
    if not isinstance(sql, str):
        return sql, params
    if isinstance(params, Mapping):
        return text(sql), dict(params)
    values = list(params or ())
    placeholder_count = sql.count("?")
    if placeholder_count != len(values):
        if placeholder_count == 0 and not values:
            return text(sql), {}
        raise ValueError(
            f"SQL placeholder count ({placeholder_count}) does not match "
            f"parameter count ({len(values)})."
        )
    pieces = sql.split("?")
    converted = pieces[0]
    bindings = {}
    for index, value in enumerate(values):
        key = f"p{index}"
        converted += f":{key}" + pieces[index + 1]
        bindings[key] = value
    return text(converted), bindings


class DatabaseRow(Mapping):
    """Mapping row that also supports integer-index access."""

    def __init__(self, row):
        self._values = tuple(row)
        self._mapping = dict(row._mapping)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self):
        return len(self._mapping)


class DatabaseResult:
    def __init__(self, result):
        self._result = result

    @property
    def rowcount(self):
        return self._result.rowcount

    def fetchone(self):
        row = self._result.fetchone()
        return DatabaseRow(row) if row is not None else None

    def fetchall(self):
        return [DatabaseRow(row) for row in self._result.fetchall()]

    def scalar(self):
        return self._result.scalar()


class DatabaseConnection:
    """Small compatibility adapter around a SQLAlchemy connection."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        statement, bindings = _prepare_statement(sql, params)
        return DatabaseResult(self._connection.execute(statement, bindings))

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def connect():
    """Return a PostgreSQL connection for read operations."""
    return DatabaseConnection(get_engine().connect())


def set_operator(connection, operator):
    """Set the audit operator for the current PostgreSQL transaction only."""
    connection.execute(
        "SELECT set_config('app.operator', ?, true)",
        (operator or "SSC Admin",),
    )


@contextmanager
def transaction(operator="SSC Admin", immediate=False):
    """Commit on success and roll back automatically on failure."""
    del immediate  # Kept in the signature so existing callers do not break.
    with get_engine().begin() as raw_connection:
        connection = DatabaseConnection(raw_connection)
        set_operator(connection, operator)
        yield connection


def column_exists(connection, table, column):
    return bool(
        connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema=? AND table_name=? AND column_name=?
            )
            """,
            (SCHEMA, table, column),
        ).fetchone()[0]
    )


def initialize_database():
    """Verify the Supabase schema without mutating it during app startup."""
    with connect() as connection:
        existing = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema=?
                """,
                (SCHEMA,),
            ).fetchall()
        }
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise RuntimeError(
            "Missing required Supabase tables: "
            + ", ".join(missing)
            + ". Run supabase_setup.sql in the Supabase SQL Editor."
        )


def test_connection():
    with connect() as connection:
        return connection.execute("SELECT 1").fetchone()[0] == 1


def json_loads(value):
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)
