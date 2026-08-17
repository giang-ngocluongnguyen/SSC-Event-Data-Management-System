import re
from urllib.parse import urlencode

import pandas as pd


PROFILE_COMPLETION_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSft78oYAoqBc0w_iyacr19bc0y_x6eYhOEXv-TyUoTZjOcvpA/viewform"
)

PROFILE_COMPLETION_FORM_FIELDS = {
    "event_id": "entry.1743599688",
    "event_name": "entry.973998869",
    "participant_id": "entry.1649886049",
    "registration_id": "entry.784821814",
    "participant_name": "entry.1177405081",
    "email": "entry.1511251002",
    "country": "entry.416288107",
    "notes": "entry.561797724",
}

POST_EVENT_FEEDBACK_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSfsE-6xRB1CgtE-aAPtxbttfPs8y6TlQZPFO_FXh9IrZMNi8w/viewform"
)

POST_EVENT_FEEDBACK_FORM_FIELDS = {
    "event_id": "entry.28409845",
    "event_name": "entry.13036103",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

DEFAULT_WORKSHEET = "Form Responses 1"


def build_profile_completion_url(attendee, event=None):
    """Build the SSC Google Form pre-filled URL from one attendee database row."""
    event = event or {}
    params = {
        "usp": "pp_url",
        PROFILE_COMPLETION_FORM_FIELDS["event_id"]: attendee.get("event_id")
        or event.get("event_id")
        or "",
        PROFILE_COMPLETION_FORM_FIELDS["event_name"]: attendee.get("event_name")
        or event.get("event_name")
        or "",
        PROFILE_COMPLETION_FORM_FIELDS["participant_id"]: attendee.get("participant_id") or "",
        PROFILE_COMPLETION_FORM_FIELDS["registration_id"]: attendee.get("registration_id") or "",
        PROFILE_COMPLETION_FORM_FIELDS["participant_name"]: attendee.get("participant_name") or "",
        PROFILE_COMPLETION_FORM_FIELDS["email"]: attendee.get("email") or "",
        PROFILE_COMPLETION_FORM_FIELDS["country"]: attendee.get("country") or "",
        PROFILE_COMPLETION_FORM_FIELDS["notes"]: attendee.get("notes") or "",
    }
    return f"{PROFILE_COMPLETION_FORM_URL}?{urlencode(params)}"


def build_post_event_feedback_url(event):
    """Build the SSC post-event feedback Google Form URL for one event."""
    params = {
        "usp": "pp_url",
        POST_EVENT_FEEDBACK_FORM_FIELDS["event_id"]: event.get("event_id") or "",
        POST_EVENT_FEEDBACK_FORM_FIELDS["event_name"]: event.get("event_name") or "",
    }
    return f"{POST_EVENT_FEEDBACK_FORM_URL}?{urlencode(params)}"


def _section(secrets, name):
    try:
        section = secrets.get(name, {})
    except Exception:
        return {}
    return dict(section) if section else {}


def _spreadsheet_id(value):
    value = str(value or "").strip()
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", value)
    return match.group(1) if match else value


def google_sheet_settings(secrets):
    google = _section(secrets, "google_sheets")
    return {
        "spreadsheet": google.get("profile_completion_spreadsheet")
        or google.get("profile_completion_spreadsheet_id")
        or google.get("profile_completion_spreadsheet_url"),
        "worksheet": google.get("profile_completion_worksheet") or DEFAULT_WORKSHEET,
    }


def is_configured(secrets):
    service_account = _section(secrets, "gcp_service_account")
    settings = google_sheet_settings(secrets)
    required = {"type", "project_id", "private_key", "client_email", "token_uri"}
    return bool(settings["spreadsheet"]) and required.issubset(service_account)


def missing_setup_items(secrets):
    missing = []
    settings = google_sheet_settings(secrets)
    service_account = _section(secrets, "gcp_service_account")
    if not settings["spreadsheet"]:
        missing.append("[google_sheets].profile_completion_spreadsheet")
    for key in ["type", "project_id", "private_key", "client_email", "token_uri"]:
        if not service_account.get(key):
            missing.append(f"[gcp_service_account].{key}")
    return missing


def load_profile_completion_responses(secrets, worksheet_name=None):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise RuntimeError(
            "Install Google Sheet dependencies first: "
            "pip install gspread google-auth"
        ) from exc

    if not is_configured(secrets):
        missing = ", ".join(missing_setup_items(secrets))
        raise ValueError(f"Google Sheet access is not configured yet. Missing: {missing}")

    settings = google_sheet_settings(secrets)
    service_account = _section(secrets, "gcp_service_account")
    if service_account.get("private_key"):
        service_account["private_key"] = service_account["private_key"].replace("\\n", "\n")

    credentials = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(_spreadsheet_id(settings["spreadsheet"]))
    worksheet = spreadsheet.worksheet(worksheet_name or settings["worksheet"])
    return pd.DataFrame(worksheet.get_all_records())
