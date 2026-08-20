import json
from contextlib import contextmanager

import streamlit as st
from sqlalchemy import URL, create_engine, text


MASTER_TABLES = [
    "events",
    "locations",
    "event_types",
    "participants",
    "partners",
]

TRANSACTION_TABLES = [
    "event_registration",
    "event_registered_attendee",
]

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


@st.cache_resource
def get_engine():
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
        connect_args={
            "sslmode": config.get("sslmode", "require"),
        },
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=2,
    )


def connect():
    """Return a PostgreSQL SQLAlchemy connection."""
    return get_engine().connect()


def set_operator(connection, operator):
    """
    Store the operator for the current transaction.

    PostgreSQL audit triggers can read this value using:
    current_setting('app.operator', true)
    """
    connection.execute(
        text(
            """
            SELECT set_config(
                'app.operator',
                :operator,
                true
            )
            """
        ),
        {"operator": operator or "SSC Admin"},
    )


@contextmanager
def transaction(operator="SSC Admin", immediate=False):
    """
    Open a PostgreSQL transaction.

    `immediate` is retained temporarily so existing function calls do not
    break, but PostgreSQL does not use SQLite's BEGIN IMMEDIATE.
    """
    del immediate

    with get_engine().begin() as connection:
        set_operator(connection, operator)
        yield connection


def table_exists(connection, table_name):
    result = connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = :table_name
            )
            """
        ),
        {
            "schema": SCHEMA,
            "table_name": table_name,
        },
    )

    return bool(result.scalar())


def column_exists(connection, table_name, column_name):
    result = connection.execute(
        text(
            """
            SELECT EXISTS (
                           SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {
            "schema": SCHEMA,
            "table_name": table_name,
            "column_name": column_name,
        },
    )

    return bool(result.scalar())


def initialize_database():
    """
    Verify that the required Supabase tables exist.

    Table creation and schema migrations should be performed in Supabase,
    not every time Streamlit starts.
    """
    required_tables = set(MASTER_TABLES + TRANSACTION_TABLES)

    with get_engine().connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                """
            ),
            {"schema": SCHEMA},
        )

        existing_tables = set(result.scalars().all())

    missing_tables = required_tables - existing_tables

    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(
            f"Missing Supabase tables in schema '{SCHEMA}': {missing}"
        )


def test_connection():
    with get_engine().connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1


def json_loads(value):
    if value is None or value == "":
        return None

    # PostgreSQL JSON/JSONB may already be converted to Python.
    if isinstance(value, (dict, list)):
        return value

    return json.loads(value)
