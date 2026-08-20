import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from database import (
    MASTER_TABLES,
    TRANSACTION_TABLES,
    _prepare_statement,
    connect,
    get_engine,
    json_loads,
    transaction,
)


CHANNELS = ["Connect", "Whatsapp", "Walk-in"]
REGISTRATION_STATUSES = ["Registered", "Cancelled", "Waitlisted"]
ATTENDANCE_STATUSES = ["Not Checked In", "Attended", "No Show", "Cancelled"]
ROLES = ["Main Attendee", "Guest"]
PARTNER_STATUSES = ["Active", "Inactive"]
BOOL_OPTIONS = ["Unknown / not filled", "Yes", "No"]
DOB_MIN = date(1900, 1, 1)
DOB_MAX = date.today()
EVENT_IMAGE_DIR = Path(__file__).parent / "assets" / "event_images"

TABLES = [
    "events",
    "locations",
    "event_types",
    "participants",
    "partners",
    "event_registration",
    "event_registered_attendee",
]
PK_COLUMNS = {
    "events": ["event_id"],
    "locations": ["location_id"],
    "event_types": ["etype_id"],
    "participants": ["participant_id"],
    "partners": ["partner_id"],
    "event_registration": ["registration_id"],
    "event_registered_attendee": ["registration_id", "participant_id"],
}
EDITABLE_COLUMNS = {
    "events": ["location_id", "event_type", "partner_id", "event_name", "start_datetime", "end_datetime", "age_rating", "ticket_cost", "accessibility", "event_image_path", "is_archived"],
    "locations": ["location_name", "street_number", "postal_code", "city", "country", "is_archived"],
    "event_types": ["etype_name", "is_archived"],
    "participants": ["participant_name", "email", "phone_number", "address", "city", "country", "dob", "whatsapp_groupchat", "have_connect", "marketing_subs", "is_archived"],
    "partners": ["partner_name", "partner_type", "street_number", "postal_code", "city", "country", "contact_person", "phone_number", "email_address", "website", "status", "partner_since", "is_archived"],
    "event_registration": ["channel", "status", "notes"],
    "event_registered_attendee": ["role", "need_buddy", "attendance_status", "checkin_datetime"],
}
BOOLEAN_COLUMNS = {
    "is_archived",
    "need_buddy",
    "whatsapp_groupchat",
    "have_connect",
    "marketing_subs",
}


def now_iso():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def current_operator():
    try:
        import streamlit as st
        return st.session_state.get("operator_name", "SSC Admin")
    except Exception:
        return "SSC Admin"


def rows(sql, params=()):
    with connect() as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def dataframe(sql, params=()):
    statement, bindings = _prepare_statement(sql, params)
    with get_engine().connect() as connection:
        return pd.read_sql_query(statement, connection, params=bindings)


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value if value != "" else None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _one(connection, sql, params=()):
    row = connection.execute(sql, params).fetchone()
    return dict(row) if row else None


def bool_to_db(label):
    if label == "Unknown / not filled":
        return None
    return label == "Yes"


def db_to_bool_label(value):
    if value is None or pd.isna(value):
        return "Unknown / not filled"
    return "Yes" if bool(value) else "No"


def dob_to_date(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _active_filter(alias=""):
    prefix = f"{alias}." if alias else ""
    return f"COALESCE({prefix}is_archived, FALSE) IS FALSE"


def events(include_archived=False):
    archive_filter = "1=1" if include_archived else _active_filter("e")
    return rows(
        f"""
        SELECT e.event_id, e.event_name, e.start_datetime, e.end_datetime,
               e.age_rating, e.ticket_cost, e.accessibility, e.event_image_path, e.is_archived,
               e.location_id, l.location_name, l.street_number, l.postal_code,
               l.city AS location_city, l.country AS location_country,
               e.event_type, et.etype_name,
               e.partner_id, p.partner_name
        FROM events e
        LEFT JOIN locations l ON l.location_id = e.location_id
        LEFT JOIN event_types et ON et.etype_id = e.event_type
        LEFT JOIN partners p ON p.partner_id = e.partner_id
        WHERE {archive_filter}
        ORDER BY e.start_datetime DESC
        """
    )


def event_by_id(event_id):
    matching = [row for row in events(include_archived=True) if int(row["event_id"]) == int(event_id)]
    return matching[0] if matching else None


def participants(include_archived=False):
    where = "1=1" if include_archived else _active_filter()
    return rows(f"SELECT * FROM participants WHERE {where} ORDER BY lower(participant_name)")


def partners(include_archived=False):
    where = "1=1" if include_archived else _active_filter()
    return rows(f"SELECT * FROM partners WHERE {where} ORDER BY lower(partner_name)")


def active_partners():
    return rows("SELECT * FROM partners WHERE status='Active' AND COALESCE(is_archived, FALSE) IS FALSE ORDER BY lower(partner_name)")


def locations(include_archived=False):
    where = "1=1" if include_archived else _active_filter()
    return rows(f"SELECT * FROM locations WHERE {where} ORDER BY location_name")


def event_types(include_archived=False):
    where = "1=1" if include_archived else _active_filter()
    return rows(f"SELECT * FROM event_types WHERE {where} ORDER BY etype_name")


def event_stats():
    return rows(
        """
        SELECT e.event_id,
               COUNT(DISTINCT CASE WHEN er.status != 'Cancelled' THEN er.registration_id END) AS registration_count,
               COUNT(CASE WHEN er.status != 'Cancelled' THEN era.participant_id END) AS attendee_count,
               SUM(CASE WHEN er.status != 'Cancelled' AND era.attendance_status='Attended' THEN 1 ELSE 0 END) AS attended_count,
               SUM(CASE WHEN er.status != 'Cancelled' AND era.attendance_status='Not Checked In' THEN 1 ELSE 0 END) AS pending_count,
               SUM(CASE WHEN er.status != 'Cancelled' AND era.attendance_status='No Show' THEN 1 ELSE 0 END) AS no_show_count
        FROM events e
        LEFT JOIN event_registration er ON er.event_id = e.event_id
        LEFT JOIN event_registered_attendee era ON era.registration_id = er.registration_id
        GROUP BY e.event_id
        """
    )


def events_with_stats(include_archived=False):
    event_df = pd.DataFrame(events(include_archived=include_archived))
    if event_df.empty:
        return []
    stats_df = pd.DataFrame(event_stats())
    merged = event_df.merge(stats_df, on="event_id", how="left")
    for column in ["registration_count", "attendee_count", "attended_count", "pending_count", "no_show_count"]:
        merged[column] = merged[column].fillna(0).astype(int)
    return merged.to_dict("records")


def home_past_kpis():
    with connect() as connection:
        result = _one(
            connection,
            """
            SELECT
                COUNT(DISTINCT e.event_id) AS total_events,
                COUNT(DISTINCT era.participant_id) AS total_participants,
                COUNT(DISTINCT er.registration_id) AS total_registrations,
                COUNT(CASE WHEN er.status != 'Cancelled' THEN era.participant_id END) AS total_attendees,
                SUM(CASE WHEN er.status != 'Cancelled' AND era.attendance_status='Attended' THEN 1 ELSE 0 END) AS attended
            FROM events e
            LEFT JOIN event_registration er ON er.event_id = e.event_id
            LEFT JOIN event_registered_attendee era ON era.registration_id = er.registration_id
            WHERE e.end_datetime < CURRENT_TIMESTAMP
              AND COALESCE(e.is_archived, FALSE) IS FALSE
            """
        )
    total_attendees = int(result.get("total_attendees") or 0)
    attended = int(result.get("attended") or 0)
    result["attendance_rate"] = attended / total_attendees if total_attendees else 0
    return result

def split_events_for_home():
    all_events = pd.DataFrame(events_with_stats())

    if all_events.empty:
        return [], []

    all_events["start_ts"] = pd.to_datetime(
        all_events["start_datetime"],
        errors="coerce",
        utc=True,
    )

    all_events["end_ts"] = pd.to_datetime(
        all_events["end_datetime"],
        errors="coerce",
        utc=True,
    )

    now = pd.Timestamp.now(tz="UTC")

    upcoming = (
        all_events[all_events["start_ts"] >= now]
        .sort_values("start_ts", ascending=True)
        .head(3)
    )

    past = (
        all_events[all_events["end_ts"] < now]
        .sort_values("end_ts", ascending=False)
        .head(3)
    )

    return past.to_dict("records"), upcoming.to_dict("records")




def dashboard_counts():
    with connect() as connection:
        return {
            "events": connection.execute("SELECT COUNT(*) FROM events WHERE COALESCE(is_archived, FALSE) IS FALSE").fetchone()[0],
            "participants": connection.execute("SELECT COUNT(*) FROM participants WHERE COALESCE(is_archived, FALSE) IS FALSE").fetchone()[0],
            "partners": connection.execute("SELECT COUNT(*) FROM partners WHERE COALESCE(is_archived, FALSE) IS FALSE").fetchone()[0],
            "registrations": connection.execute("SELECT COUNT(*) FROM event_registration").fetchone()[0],
            "checked_in": connection.execute("SELECT COUNT(*) FROM event_registered_attendee WHERE attendance_status='Attended'").fetchone()[0],
        }


def next_event_id_preview():
    with connect() as connection:
        return next_event_id(connection)


def registrations(event_id=None):
    where = ""
    params = ()
    if event_id is not None:
        where = "WHERE er.event_id=?"
        params = (int(event_id),)
    return rows(
        f"""
        SELECT er.registration_id, er.event_id, e.event_name, er.registered_by,
               p.participant_name AS registered_by_name, er.datetime_registered,
               er.number_of_attendee, er.channel, er.status, er.notes
        FROM event_registration er
        LEFT JOIN events e ON e.event_id = er.event_id
        LEFT JOIN participants p ON p.participant_id = er.registered_by
        {where}
        ORDER BY er.event_id DESC, er.registration_id DESC
        """,
        params,
    )


def _next_code(connection, table, column, prefix, width):
    connection.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (f"{table}.{column}",))
    values = [row[0] for row in connection.execute(f"SELECT {column} FROM {table}").fetchall()]
    maximum = 0
    for value in values:
        match = re.fullmatch(prefix + r"(\d+)", str(value or ""))
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"{prefix}{maximum + 1:0{width}d}"


def next_registration_id(connection, event_id):
    prefix = f"{int(event_id)}-"
    connection.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (f"registration:{event_id}",))
    values = connection.execute(
        "SELECT registration_id FROM event_registration WHERE event_id=? AND registration_id LIKE ?",
        (int(event_id), f"{prefix}%"),
    ).fetchall()
    maximum = 0
    for row in values:
        suffix = str(row[0] or "")[len(prefix):]
        if suffix.isdigit():
            maximum = max(maximum, int(suffix))
    return f"{prefix}{maximum + 1:03d}"


def next_event_id(connection):
    connection.execute("SELECT pg_advisory_xact_lock(hashtext('events.event_id'))")
    return int(connection.execute("SELECT COALESCE(MAX(event_id), 0) + 1 FROM events").fetchone()[0])


def make_event_type_id(connection, name):
    words = ["".join(ch for ch in word.upper() if ch.isalnum()) for word in str(name).split()]
    words = [word for word in words if word]
    if not words:
        base = "TYP"
    elif len(words) == 1:
        base = words[0][:3].ljust(3, "X")
    elif len(words) == 2:
        base = (words[0][:2] + words[1][0]).ljust(3, "X")
    else:
        base = "".join(word[0] for word in words[:3]).ljust(3, "X")
    existing = {row[0] for row in connection.execute("SELECT etype_id FROM event_types").fetchall()}
    if base not in existing:
        return base
    for number in range(2, 100):
        candidate = f"{base}{number}"
        if candidate not in existing:
            return candidate
    raise ValueError("Could not generate a unique event type ID.")


def find_participant_by_email(email):
    email = (email or "").strip().lower()
    if not email:
        return None
    with connect() as connection:
        return _one(connection, "SELECT * FROM participants WHERE lower(email)=?", (email,))


def upsert_participant(data):
    clean = {key: _blank_to_none(value) for key, value in data.items()}
    email = (clean.get("email") or "").lower() if clean.get("email") else None
    phone = clean.get("phone_number")
    with transaction(current_operator(), immediate=True) as connection:
        existing = None
        if email:
            existing = _one(connection, "SELECT * FROM participants WHERE lower(email)=?", (email,))
        if existing is None and phone:
            existing = _one(connection, "SELECT * FROM participants WHERE phone_number=?", (phone,))
        if existing:
            now = now_iso()
            connection.execute(
                """
                UPDATE participants
                SET participant_name=COALESCE(?, participant_name),
                    phone_number=COALESCE(?, phone_number),
                    address=COALESCE(?, address),
                    city=COALESCE(?, city),
                    country=COALESCE(?, country),
                    dob=COALESCE(?, dob),
                    whatsapp_groupchat=COALESCE(?, whatsapp_groupchat),
                    have_connect=COALESCE(?, have_connect),
                    marketing_subs=COALESCE(?, marketing_subs),
                    is_archived=FALSE,
                    last_updated=?
                WHERE participant_id=?
                """,
                (
                    clean.get("participant_name"), clean.get("phone_number"), clean.get("address"),
                    clean.get("city"), clean.get("country"), clean.get("dob"),
                    clean.get("whatsapp_groupchat"), clean.get("have_connect"),
                    clean.get("marketing_subs"), now, existing["participant_id"],
                ),
            )
            return existing["participant_id"], "updated"

        participant_id = _next_code(connection, "participants", "participant_id", "P", 4)
        row = {
            "participant_id": participant_id,
            "participant_name": clean.get("participant_name") or "Guest",
            "email": email,
            "phone_number": clean.get("phone_number"),
            "address": clean.get("address"),
            "city": clean.get("city"),
            "country": clean.get("country") or "NL",
            "dob": clean.get("dob"),
            "whatsapp_groupchat": clean.get("whatsapp_groupchat"),
            "have_connect": clean.get("have_connect"),
            "marketing_subs": clean.get("marketing_subs"),
            "is_archived": False,
            "last_updated": now_iso(),
        }
        fields = list(row)
        connection.execute(
            f"INSERT INTO participants ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            [row[field] for field in fields],
        )
        return participant_id, "created"


def participant_already_registered(connection, event_id, participant_id):
    return connection.execute(
        """
        SELECT 1
        FROM event_registration er
        JOIN event_registered_attendee era ON era.registration_id = er.registration_id
        WHERE er.event_id=? AND era.participant_id=? AND er.status != 'Cancelled'
        LIMIT 1
        """,
        (int(event_id), participant_id),
    ).fetchone() is not None


def existing_registration_by_email(event_id, email):
    email = (email or "").strip().lower()
    if not email:
        return None
    with connect() as connection:
        return _one(
            connection,
            """
            SELECT er.registration_id, er.status, p.participant_name, p.email, era.role, era.attendance_status
            FROM event_registration er
            JOIN event_registered_attendee era ON era.registration_id=er.registration_id
            JOIN participants p ON p.participant_id=era.participant_id
            WHERE er.event_id=? AND lower(p.email)=? AND er.status != 'Cancelled'
            ORDER BY er.registration_id DESC
            LIMIT 1
            """,
            (int(event_id), email),
        )


def create_registration_group(event_id, registered_by, attendees, channel, notes=None, immediate_checkin=False):
    valid = []
    skipped = []
    with transaction(current_operator(), immediate=True) as connection:
        for attendee in attendees:
            if participant_already_registered(connection, event_id, attendee["participant_id"]):
                skipped.append(attendee.get("label") or attendee["participant_id"])
            else:
                valid.append(attendee)
        if not valid:
            return None, skipped

        registration_id = next_registration_id(connection, event_id)
        now = now_iso()
        status = "Attended" if immediate_checkin else "Not Checked In"
        checkin_datetime = now if immediate_checkin else None
        connection.execute(
            """
            INSERT INTO event_registration
            (registration_id, registered_by, event_id, datetime_registered, number_of_attendee, channel, status, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, 'Registered', ?, ?)
            """,
            (registration_id, registered_by, int(event_id), now, len(valid), channel, _blank_to_none(notes), now),
        )
        for attendee in valid:
            connection.execute(
                """
                INSERT INTO event_registered_attendee
                (registration_id, participant_id, role, need_buddy, attendance_status, checkin_datetime, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registration_id,
                    attendee["participant_id"],
                    attendee.get("role") or "Guest",
                    attendee.get("need_buddy"),
                    status,
                    checkin_datetime,
                    now,
                ),
            )
        return registration_id, skipped


def attendee_rows(event_id, include_attended=True):
    attended_filter = "" if include_attended else "AND era.attendance_status != 'Attended'"
    return rows(
        f"""
        SELECT era.registration_id, er.registered_by, rb.participant_name AS registered_by_name,
               era.participant_id, p.participant_name, p.email, p.phone_number, p.address, p.city, p.country,
               p.dob, p.whatsapp_groupchat, p.have_connect, p.marketing_subs,
               era.role, era.need_buddy, era.attendance_status, era.checkin_datetime,
               er.channel, er.status AS registration_status, er.notes, er.datetime_registered,
               er.number_of_attendee,
               CASE WHEN er.number_of_attendee = 1 THEN 'Solo' ELSE 'Group' END AS registration_type
        FROM event_registration er
        JOIN event_registered_attendee era ON era.registration_id = er.registration_id
        JOIN participants p ON p.participant_id = era.participant_id
        LEFT JOIN participants rb ON rb.participant_id = er.registered_by
        WHERE er.event_id=? AND er.status != 'Cancelled' {attended_filter}
        ORDER BY CASE WHEN era.attendance_status='Attended' THEN 1 ELSE 0 END,
                 era.registration_id, lower(p.participant_name)
        """,
        (int(event_id),),
    )


def filter_attendees(attendees, search):
    if not search:
        return attendees
    query = search.lower().strip()
    fields = [
        "registration_id", "participant_name", "role", "registered_by_name",
        "email", "phone_number", "channel", "attendance_status",
        "registration_status", "address", "city", "country",
    ]
    matched_codes = set()
    for row in attendees:
        if any(query in str(row.get(field) or "").lower() for field in fields):
            matched_codes.add(row["registration_id"])
    return [row for row in attendees if row["registration_id"] in matched_codes]


def check_in(registration_id, participant_id):
    with transaction(current_operator(), immediate=True) as connection:
        result = connection.execute(
            """
            UPDATE event_registered_attendee
            SET attendance_status='Attended', checkin_datetime=CURRENT_TIMESTAMP, last_updated=CURRENT_TIMESTAMP
            WHERE registration_id=? AND participant_id=? AND attendance_status != 'Attended'
            """,
            (registration_id, participant_id),
        )
        return result.rowcount


PROFILE_IMPORT_ALIASES = {
    "registration_id": {
        "registration_id", "registrationid", "registration_code", "registrationcode",
        "registration", "code", "for_ssc_use_only_registration_code",
        "ssc_registration_code",
    },
    "participant_id": {
        "participant_id", "participantid", "person_id", "personid",
        "for_ssc_use_only_participant_id", "ssc_participant_id",
    },
    "participant_name": {
        "participant_name", "participantname", "name", "full_name", "fullname",
        "participant", "attendee_name", "attendeename",
    },
    "email": {"email", "email_address", "emailaddress", "e_mail"},
    "phone_number": {"phone", "phone_number", "phonenumber", "mobile", "mobile_number", "whatsapp", "whatsapp_number"},
    "address": {"address", "street_address", "streetaddress"},
    "city": {"city", "place_of_residence", "residence", "woonplaats"},
    "country": {"country", "country_code", "countrycode", "nationality"},
    "dob": {"dob", "date_of_birth", "dateofbirth", "birth_date", "birthdate"},
    "whatsapp_groupchat": {"whatsapp_groupchat", "whatsappgroupchat", "in_whatsapp_groupchat", "inwhatsappgroupchat", "in_groupchat"},
    "have_connect": {
        "have_connect", "haveconnect", "connect", "connect_account", "has_connect_account",
        "hasconnectaccount", "had_ssc_connect_account", "hadsscconnectaccount",
        "has_ssc_connect_account", "hassscconnectaccount", "ssc_connect_account",
        "sscconnectaccount",
    },
    "marketing_subs": {
        "marketing_subs", "marketingsubs", "marketing_subscription", "marketingsubscription",
        "newsletter", "consent", "consent_to_update_profile", "consenttoupdateprofile",
    },
}


def _normalise_import_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _import_value(record, canonical_key):
    aliases = {_normalise_import_key(alias) for alias in PROFILE_IMPORT_ALIASES[canonical_key]}
    for key, value in record.items():
        if _normalise_import_key(key) in aliases:
            return _blank_to_none(value)
    return None


def _normalise_bool_import(value):
    value = _blank_to_none(value)
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "ja", "checked", "agree", "agreed"}:
        return True
    if text in {"0", "false", "no", "n", "nee", "not checked", "disagree", "declined"}:
        return False
    return None


def _normalise_date_import(value):
    value = _blank_to_none(value)
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _clean_profile_import_record(record):
    clean = {
        "registration_id": _import_value(record, "registration_id"),
        "participant_id": _import_value(record, "participant_id"),
        "participant_name": _import_value(record, "participant_name"),
        "email": _import_value(record, "email"),
        "phone_number": _import_value(record, "phone_number"),
        "address": _import_value(record, "address"),
        "city": _import_value(record, "city"),
        "country": _import_value(record, "country"),
        "dob": _normalise_date_import(_import_value(record, "dob")),
        "whatsapp_groupchat": _normalise_bool_import(_import_value(record, "whatsapp_groupchat")),
        "have_connect": _normalise_bool_import(_import_value(record, "have_connect")),
        "marketing_subs": _normalise_bool_import(_import_value(record, "marketing_subs")),
    }
    if clean["email"]:
        clean["email"] = str(clean["email"]).strip().lower()
    if clean["registration_id"]:
        clean["registration_id"] = str(clean["registration_id"]).strip()
    if clean["participant_id"]:
        clean["participant_id"] = str(clean["participant_id"]).strip()
    return clean


def _registration_attendee_targets(connection, registration_id, event_id=None):
    event_filter = "" if event_id is None else "AND er.event_id=?"
    params = [str(registration_id)]
    if event_id is not None:
        params.append(int(event_id))
    return [
        dict(row)
        for row in connection.execute(
            f"""
            SELECT era.participant_id, p.participant_name, p.email, p.phone_number
            FROM event_registered_attendee era
            JOIN event_registration er ON er.registration_id = era.registration_id
            JOIN participants p ON p.participant_id = era.participant_id
            WHERE era.registration_id=? {event_filter}
            """,
            params,
        ).fetchall()
    ]


def _find_profile_import_target(connection, clean, event_id=None):
    participant_id = clean.get("participant_id")
    registration_id = clean.get("registration_id")
    email = clean.get("email")
    phone = clean.get("phone_number")
    name = (clean.get("participant_name") or "").strip().lower()

    if participant_id:
        row = connection.execute(
            "SELECT participant_id FROM participants WHERE participant_id=?",
            (participant_id,),
        ).fetchone()
        if row:
            return participant_id, None

    if registration_id:
        targets = _registration_attendee_targets(connection, registration_id, event_id)
        if not targets:
            return None, f"No attendee found for registration {registration_id}."
        if participant_id:
            for target in targets:
                if str(target["participant_id"]) == participant_id:
                    return target["participant_id"], None
        if email:
            for target in targets:
                if (target.get("email") or "").strip().lower() == email:
                    return target["participant_id"], None
        if name:
            for target in targets:
                if (target.get("participant_name") or "").strip().lower() == name:
                    return target["participant_id"], None
        if len(targets) == 1:
            return targets[0]["participant_id"], None
        return None, f"Registration {registration_id} has multiple attendees; include participant_id, email, or exact name."

    if email:
        row = connection.execute(
            "SELECT participant_id FROM participants WHERE lower(email)=?",
            (email,),
        ).fetchone()
        if row:
            return row["participant_id"], None

    if phone:
        row = connection.execute(
            "SELECT participant_id FROM participants WHERE phone_number=?",
            (phone,),
        ).fetchone()
        if row:
            return row["participant_id"], None

    return None, "No match. Include registration_id or participant_id."


def import_profile_completion_responses(records, event_id=None):
    result = {"updated": 0, "skipped": 0, "errors": []}
    editable_fields = [
        "participant_name", "email", "phone_number", "address", "city", "country",
        "dob", "whatsapp_groupchat", "have_connect", "marketing_subs",
    ]
    with transaction(current_operator(), immediate=True) as connection:
        for row_number, record in enumerate(records, start=2):
            clean = _clean_profile_import_record(record)
            participant_id, error = _find_profile_import_target(connection, clean, event_id)
            if error:
                result["skipped"] += 1
                result["errors"].append({"row": row_number, "reason": error})
                continue

            changes = {
                field: clean[field]
                for field in editable_fields
                if clean.get(field) is not None
            }
            if not changes:
                result["skipped"] += 1
                result["errors"].append({"row": row_number, "reason": "No usable profile fields found."})
                continue

            assignments = ", ".join(f"{field}=?" for field in changes)
            connection.execute(
                f"UPDATE participants SET {assignments}, is_archived=FALSE, last_updated=? WHERE participant_id=?",
                [*changes.values(), now_iso(), participant_id],
            )
            result["updated"] += 1
    return result


def update_participant(participant_id, changes):
    return update_record("participants", {"participant_id": participant_id}, changes)


def create_event(data):
    clean = {key: _blank_to_none(value) for key, value in data.items()}
    with transaction(current_operator(), immediate=True) as connection:
        event_id = next_event_id(connection)
        clean["event_id"] = event_id
        clean["is_archived"] = False
        clean["last_updated"] = now_iso()
        fields = ["event_id", "location_id", "event_type", "partner_id", "event_name", "start_datetime", "end_datetime", "age_rating", "ticket_cost", "accessibility", "event_image_path", "is_archived", "last_updated"]
        connection.execute(
            f"INSERT INTO events ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            [clean.get(field) for field in fields],
        )
        return event_id


def save_event_image(event_id, uploaded_file):
    if uploaded_file is None:
        return None
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Event image must be PNG, JPG, JPEG, or WEBP.")
    EVENT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"event_{int(event_id)}{suffix}"
    path = EVENT_IMAGE_DIR / filename
    path.write_bytes(uploaded_file.getvalue())
    relative_path = f"assets/event_images/{filename}"
    update_record("events", {"event_id": int(event_id)}, {"event_image_path": relative_path})
    return relative_path


def create_location(data):
    clean = {key: _blank_to_none(value) for key, value in data.items()}
    with transaction(current_operator(), immediate=True) as connection:
        clean["location_id"] = _next_code(connection, "locations", "location_id", "L", 3)
        clean["is_archived"] = False
        clean["last_updated"] = now_iso()
        fields = ["location_id", "location_name", "street_number", "postal_code", "city", "country", "is_archived", "last_updated"]
        connection.execute(
            f"INSERT INTO locations ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            [clean.get(field) for field in fields],
        )
        return clean["location_id"]


def create_event_type(name):
    with transaction(current_operator(), immediate=True) as connection:
        etype_id = make_event_type_id(connection, name)
        connection.execute(
            "INSERT INTO event_types (etype_id, etype_name, is_archived, last_updated) VALUES (?, ?, FALSE, ?)",
            (etype_id, name.strip(), now_iso()),
        )
        return etype_id


def create_partner(data):
    clean = {key: _blank_to_none(value) for key, value in data.items()}
    with transaction(current_operator(), immediate=True) as connection:
        clean["partner_id"] = _next_code(connection, "partners", "partner_id", "PAR", 3)
        clean["is_archived"] = False
        clean["last_updated"] = now_iso()
        fields = ["partner_id", "partner_name", "partner_type", "street_number", "postal_code", "city",
                  "country", "contact_person", "phone_number", "email_address", "website", "status", "partner_since", "is_archived", "last_updated"]
        connection.execute(
            f"INSERT INTO partners ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            [clean.get(field) for field in fields],
        )
        return clean["partner_id"]


def mark_remaining_no_show(event_id):
    with transaction(current_operator(), immediate=True) as connection:
        result = connection.execute(
            """
            UPDATE event_registered_attendee
            SET attendance_status='No Show', last_updated=CURRENT_TIMESTAMP
            WHERE registration_id IN (
                SELECT registration_id FROM event_registration WHERE event_id=? AND status != 'Cancelled'
            )
            AND attendance_status='Not Checked In'
            """,
            (int(event_id),),
        )
        return result.rowcount


def table_columns(table):
    if table not in TABLES:
        raise ValueError("Unsupported table.")
    return rows(
        """
        SELECT column_name AS name, data_type AS type, is_nullable
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=?
        ORDER BY ordinal_position
        """,
        (table,),
    )


def table_records(table, include_archived=True, limit=500):
    if table not in TABLES:
        raise ValueError("Unsupported table.")
    where = ""
    if table in MASTER_TABLES and not include_archived:
        where = "WHERE COALESCE(is_archived, FALSE) IS FALSE"
    order_cols = ", ".join(PK_COLUMNS[table])
    return rows(f"SELECT * FROM {table} {where} ORDER BY {order_cols} LIMIT ?", (int(limit),))


def record_label(table, record):
    pk = PK_COLUMNS[table]
    return " / ".join(str(record[column]) for column in pk)


def update_record(table, pk_values, changes):
    if table not in TABLES:
        raise ValueError("Unsupported table.")
    clean = {
        key: _blank_to_none(value)
        for key, value in changes.items()
        if key in EDITABLE_COLUMNS[table] and key not in PK_COLUMNS[table]
    }
    for key in BOOLEAN_COLUMNS & clean.keys():
        if clean[key] is not None:
            clean[key] = bool(clean[key])
    if not clean:
        return 0
    where = " AND ".join(f"{column}=?" for column in PK_COLUMNS[table])
    params = [*clean.values(), now_iso(), *[pk_values[column] for column in PK_COLUMNS[table]]]
    with transaction(current_operator(), immediate=True) as connection:
        result = connection.execute(
            f"UPDATE {table} SET {', '.join(column + '=?' for column in clean)}, last_updated=? WHERE {where}",
            params,
        )
        return result.rowcount


def archive_record(table, pk_values):
    if table in MASTER_TABLES:
        return update_record(table, pk_values, {"is_archived": True})
    if table == "event_registration":
        return update_record(table, pk_values, {"status": "Cancelled"})
    if table == "event_registered_attendee":
        return update_record(table, pk_values, {"attendance_status": "Cancelled"})
    raise ValueError("Archive is not supported for this table.")


def delete_transactional_record(table, pk_values):
    if table not in TRANSACTION_TABLES:
        raise ValueError("Only transactional rows can be deleted in this demo.")
    with transaction(current_operator(), immediate=True) as connection:
        if table == "event_registration":
            connection.execute("DELETE FROM event_registered_attendee WHERE registration_id=?", (pk_values["registration_id"],))
            result = connection.execute("DELETE FROM event_registration WHERE registration_id=?", (pk_values["registration_id"],))
            return result.rowcount
        result = connection.execute(
            "DELETE FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
            (pk_values["registration_id"], pk_values["participant_id"]),
        )
        connection.execute(
            """
            UPDATE event_registration
            SET number_of_attendee = (
                SELECT COUNT(*) FROM event_registered_attendee WHERE registration_id=?
            ),
            last_updated=CURRENT_TIMESTAMP
            WHERE registration_id=?
            """,
            (pk_values["registration_id"], pk_values["registration_id"]),
        )
        return result.rowcount


def audit_entries(limit=300, table_name=None, operator_name=None, days=None):
    params = []
    filters = []
    if table_name and table_name != "All":
        filters.append("table_name=?")
        params.append(table_name)
    if operator_name and operator_name != "All":
        filters.append("operator=?")
        params.append(operator_name)
    if days and days != "All":
        filters.append("changed_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 day')")
        params.append(int(days))
    where = "WHERE " + " AND ".join(filters) if filters else ""
    params.append(int(limit))
    return rows(
        f"""
        SELECT audit_id, changed_at, table_name, record_id, action, operator, source,
               before_json, after_json, undone, undo_audit_id
        FROM audit_log
        {where}
        ORDER BY audit_id DESC
        LIMIT ?
        """,
        params,
    )


def audit_operators():
    return [row["operator"] for row in rows("SELECT DISTINCT operator FROM audit_log WHERE operator IS NOT NULL ORDER BY operator")]


def audit_change_summary(entry):
    before = audit_payload(entry, "before_json") or {}
    after = audit_payload(entry, "after_json") or {}
    if entry["action"] == "INSERT":
        return "Created record"
    if entry["action"] == "DELETE":
        return "Deleted record"
    changed = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changed.append(key)
    return ", ".join(changed[:8]) + ("..." if len(changed) > 8 else "") if changed else "No field-level change detected"


def undo_update(audit_id):
    with transaction(current_operator(), immediate=True) as connection:
        entry = _one(connection, "SELECT * FROM audit_log WHERE audit_id=?", (int(audit_id),))
        if not entry:
            raise ValueError("Audit entry not found.")
        if entry["action"] != "UPDATE":
            raise ValueError("Only UPDATE actions are supported for undo in this demo.")
        if bool(entry.get("undone")):
            raise ValueError("This audit entry was already undone.")
        table = entry["table_name"]
        if table not in TABLES:
            raise ValueError("Unsupported table.")
        before = json_loads(entry["before_json"])
        if not before:
            raise ValueError("This entry has no before state.")
        pk_cols = PK_COLUMNS[table]
        editable = [column for column in before if column not in pk_cols and column in EDITABLE_COLUMNS[table]]
        if not editable:
            raise ValueError("No editable columns available to restore.")
        where = " AND ".join(f"{column}=?" for column in pk_cols)
        connection.execute(
            f"UPDATE {table} SET {', '.join(column + '=?' for column in editable)}, last_updated=CURRENT_TIMESTAMP WHERE {where}",
            [*[before[column] for column in editable], *[before[column] for column in pk_cols]],
        )
        undo_id = connection.execute(
            "SELECT MAX(audit_id) FROM audit_log WHERE transaction_id=txid_current()"
        ).fetchone()[0]
        connection.execute(
            "UPDATE audit_log SET undone=TRUE, undo_audit_id=? WHERE audit_id=?",
            (undo_id, int(audit_id)),
        )
        return undo_id


def audit_payload(entry, key):
    return json_loads(entry.get(key))
