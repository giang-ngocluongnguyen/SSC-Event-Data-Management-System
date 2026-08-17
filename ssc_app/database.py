import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(__file__).parent / "ssc_database.db"

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


def connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def set_operator(connection, operator):
    connection.execute(
        """
        INSERT INTO audit_context (id, operator)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET operator=excluded.operator
        """,
        (operator or "SSC Admin",),
    )


@contextmanager
def transaction(operator="SSC Admin", immediate=False):
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        set_operator(connection, operator)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def column_exists(connection, table, column):
    return column in [row["name"] for row in connection.execute(f"PRAGMA table_info({table})")]


def _json_object(columns, alias):
    parts = []
    for column in columns:
        quoted = '"' + column.replace('"', '""') + '"'
        parts.append(f"'{column}', {alias}.{quoted}")
    return "json_object(" + ", ".join(parts) + ")"


def _record_expr(pk_columns, alias):
    parts = []
    for index, column in enumerate(pk_columns):
        if index:
            parts.append("'/'")
        quoted = '"' + column.replace('"', '""') + '"'
        parts.append(f"{alias}.{quoted}")
    return " || ".join(parts)


def _drop_old_audit_triggers(connection, table_name):
    for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND name LIKE 'audit_%'",
        (table_name,),
    ):
        connection.execute(f"DROP TRIGGER IF EXISTS {row['name']}")


def _create_audit_triggers(connection, table_name, pk_columns):
    columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")]
    if not columns:
        return

    before_json = _json_object(columns, "OLD")
    after_json = _json_object(columns, "NEW")
    new_record_expr = _record_expr(pk_columns, "NEW")
    old_record_expr = _record_expr(pk_columns, "OLD")
    safe_name = table_name.replace("_", "")
    operator_expr = "COALESCE((SELECT operator FROM audit_context WHERE id=1), 'SSC Admin')"

    _drop_old_audit_triggers(connection, table_name)
    connection.executescript(
        f"""
        CREATE TRIGGER audit_{safe_name}_insert
        AFTER INSERT ON {table_name}
        BEGIN
            INSERT INTO audit_log
                (table_name, record_id, action, operator, source, before_json, after_json)
            VALUES
                ('{table_name}', {new_record_expr} || '', 'INSERT', {operator_expr}, 'sqlite_trigger', NULL, {after_json});
        END;

        CREATE TRIGGER audit_{safe_name}_update
        AFTER UPDATE ON {table_name}
        BEGIN
            INSERT INTO audit_log
                (table_name, record_id, action, operator, source, before_json, after_json)
            VALUES
                ('{table_name}', {new_record_expr} || '', 'UPDATE', {operator_expr}, 'sqlite_trigger', {before_json}, {after_json});
        END;

        CREATE TRIGGER audit_{safe_name}_delete
        AFTER DELETE ON {table_name}
        BEGIN
            INSERT INTO audit_log
                (table_name, record_id, action, operator, source, before_json, after_json)
            VALUES
                ('{table_name}', {old_record_expr} || '', 'DELETE', {operator_expr}, 'sqlite_trigger', {before_json}, NULL);
        END;
        """
    )


def _ensure_audit_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_context (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            operator TEXT
        )
        """
    )
    connection.execute("INSERT OR IGNORE INTO audit_context (id, operator) VALUES (1, 'SSC Admin')")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            table_name TEXT NOT NULL,
            record_id TEXT,
            action TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
            operator TEXT,
            source TEXT DEFAULT 'sqlite_trigger',
            before_json TEXT,
            after_json TEXT,
            undone INTEGER DEFAULT 0,
            undo_audit_id INTEGER
        )
        """
    )
    if not column_exists(connection, "audit_log", "undone"):
        connection.execute("ALTER TABLE audit_log ADD COLUMN undone INTEGER DEFAULT 0")
    if not column_exists(connection, "audit_log", "undo_audit_id"):
        connection.execute("ALTER TABLE audit_log ADD COLUMN undo_audit_id INTEGER")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_table_record "
        "ON audit_log(table_name, record_id, changed_at)"
    )


def _ensure_archive_columns(connection):
    for table in MASTER_TABLES:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists and not column_exists(connection, table, "is_archived"):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN is_archived INTEGER DEFAULT 0")


def _ensure_event_image_column(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'",
    ).fetchone()
    if exists and not column_exists(connection, "events", "event_image_path"):
        connection.execute("ALTER TABLE events ADD COLUMN event_image_path TEXT")


def _ensure_last_updated_columns(connection):
    for table in AUDITED_TABLES:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            continue
        if not column_exists(connection, table, "last_updated"):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN last_updated TEXT")
        connection.execute(
            f"UPDATE {table} SET last_updated=COALESCE(last_updated, CURRENT_TIMESTAMP)"
        )


def initialize_database():
    with connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        _ensure_audit_schema(connection)
        _ensure_archive_columns(connection)
        _ensure_event_image_column(connection)
        _ensure_last_updated_columns(connection)
        for table_name, pk_columns in AUDITED_TABLES.items():
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            if exists:
                _create_audit_triggers(connection, table_name, pk_columns)
        connection.commit()


def json_loads(value):
    if not value:
        return None
    return json.loads(value)
