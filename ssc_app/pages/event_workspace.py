import html
import re
import textwrap
import zipfile
from io import BytesIO
from urllib.parse import quote_plus, urlencode

import pandas as pd
import streamlit as st

import google_forms
import repository as repo
from layout import PINK, PRIMARY, basic_info, colored_heading, page_header

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None


page_header(
    "Event Management",
    "Event Workspace",
    "Select an event, register attendees, check people in, and close the event after it finishes.",
)


def _participant_option_label(row):
    contact_parts = [value for value in [row.get("email"), row.get("phone_number")] if value]
    contact = " | ".join(str(value) for value in contact_parts) or "No contact details"
    last_event = row.get("last_event_attended") or "No attended event"
    blocked = "🚫 BLOCKED — " if bool(row.get("blocked_flag")) else ""
    return (
        f"{blocked}{row.get('participant_name') or 'Unnamed'} — {contact} "
        f"— Last attended: {last_event} [{row['participant_id']}]"
    )


def _load_participant_choice(prefix, participant_lookup):
    choice = st.session_state.get(f"{prefix}_participant_choice")
    selected = participant_lookup.get(choice)
    if selected:
        st.session_state[f"{prefix}_participant_id"] = selected.get("participant_id")
        st.session_state[f"{prefix}_name"] = selected.get("participant_name") or ""
        st.session_state[f"{prefix}_email"] = selected.get("email") or ""
        st.session_state[f"{prefix}_phone"] = selected.get("phone_number") or ""
        st.session_state[f"{prefix}_address"] = selected.get("address") or ""
        st.session_state[f"{prefix}_city"] = selected.get("city") or ""
        st.session_state[f"{prefix}_country"] = selected.get("country") or "NL"
        st.session_state[f"{prefix}_whatsapp"] = repo.db_to_bool_label(selected.get("whatsapp_groupchat"))
        st.session_state[f"{prefix}_connect"] = repo.db_to_bool_label(selected.get("have_connect"))
        st.session_state[f"{prefix}_marketing"] = repo.db_to_bool_label(selected.get("marketing_subs"))
        return

    st.session_state[f"{prefix}_participant_id"] = None
    st.session_state[f"{prefix}_name"] = str(choice or "").strip()
    for field in ["email", "phone", "address", "city"]:
        st.session_state[f"{prefix}_{field}"] = ""
    st.session_state[f"{prefix}_country"] = "NL"
    for field in ["whatsapp", "connect", "marketing"]:
        st.session_state[f"{prefix}_{field}"] = repo.BOOL_OPTIONS[0]


def participant_inputs(prefix, participant_rows, require_contact=True):
    participant_lookup = {_participant_option_label(row): row for row in participant_rows}
    choice = st.selectbox(
        "Name *",
        list(participant_lookup),
        index=None,
        key=f"{prefix}_participant_choice",
        placeholder="Search an existing participant or enter a new name",
        accept_new_options=True,
        on_change=_load_participant_choice,
        args=(prefix, participant_lookup),
    )
    selected = participant_lookup.get(choice)
    if selected and bool(selected.get("blocked_flag")):
        st.markdown(
            "<div style='color:#d00000; font-weight:700; margin:-0.25rem 0 0.75rem;'>"
            "⚠ This participant is marked as blocked.</div>",
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        email = st.text_input("Email", key=f"{prefix}_email").strip().lower()
        phone = st.text_input("Phone number", key=f"{prefix}_phone")
        address = st.text_input("Address", key=f"{prefix}_address")
        city = st.text_input("City", key=f"{prefix}_city")
    with c2:
        country = st.text_input("Country", value="NL", key=f"{prefix}_country")
        whatsapp = st.selectbox("In WhatsApp groupchat?", repo.BOOL_OPTIONS, key=f"{prefix}_whatsapp")
        connect = st.selectbox("Has Connect account?", repo.BOOL_OPTIONS, key=f"{prefix}_connect")
        marketing = st.selectbox("Marketing subscription?", repo.BOOL_OPTIONS, key=f"{prefix}_marketing")
    return {
        "participant_id": st.session_state.get(f"{prefix}_participant_id"),
        "participant_name": st.session_state.get(f"{prefix}_name", str(choice or "").strip()),
        "email": email,
        "phone_number": phone,
        "address": address,
        "city": city,
        "country": country,
        "whatsapp_groupchat": repo.bool_to_db(whatsapp),
        "have_connect": repo.bool_to_db(connect),
        "marketing_subs": repo.bool_to_db(marketing),
        "require_contact": require_contact,
    }


def validate_person(data, label):
    if not data.get("participant_name"):
        raise ValueError(f"{label}: name is required.")
    if data.get("require_contact") and not (data.get("email") or data.get("phone_number")):
        raise ValueError(f"{label}: provide name + phone number or name + email.")


def render_registration_conflicts(event_id, label, person):
    """Show existing registrations as soon as an existing person is selected."""
    if not any(person.get(key) for key in ("participant_id", "email", "phone_number")):
        return []
    conflicts = repo.registration_conflicts_for_person(event_id, person)
    for conflict in conflicts:
        details = []
        if conflict.get("is_registrant"):
            details.append("already created a registration")
        if conflict.get("is_attendee"):
            role = conflict.get("attendee_role") or "Attendee"
            details.append(f"is already included as {role}")
        name = conflict.get("participant_name") or person.get("participant_name") or "This participant"
        next_step = (
            "They will not be added twice as an attendee."
            if conflict.get("is_attendee")
            else "Review the existing registration before creating another one."
        )
        st.warning(
            f"{label}: {name} {' and '.join(details)} "
            f"({conflict['registration_id']}). {next_step}"
        )
    return conflicts


def render_current_form_duplicates(people):
    """Warn when the same known person appears twice in the current attendee list."""
    seen = {}
    duplicates = []
    for label, person in people:
        participant_id = str(person.get("participant_id") or "").strip()
        email = str(person.get("email") or "").strip().lower()
        phone = str(person.get("phone_number") or "").strip()
        identity = (
            ("participant_id", participant_id)
            if participant_id
            else (("email", email) if email else (("phone", phone) if phone else None))
        )
        if identity is None:
            continue
        if identity in seen:
            duplicates.append(f"{label} matches {seen[identity]}")
        else:
            seen[identity] = label
    if duplicates:
        st.warning(
            "The same participant is entered more than once in this registration: "
            + "; ".join(duplicates)
            + ". Duplicate attendee rows will be skipped."
        )
    return duplicates


def registration_summary(channel, attendee_count):
    registration_type = "Solo" if attendee_count == 1 else "Group"
    with st.container(border=True):
        st.markdown("**Registration summary**")
        st.write(f"Channel: {channel}")
        st.write(f"Type: {registration_type}")
        st.write(f"Number of attendees: {attendee_count}")
    return registration_type


def selected_attendee_details(selected):
    score, _, _ = profile_completion_status(selected)
    attendee_name = selected.get("participant_name") or "-"
    fields = [
        ("Profile complete", f"{score:.0%}"),
        ("Registration code", selected.get("registration_id") or "-"),
        ("Registered by", selected.get("registered_by_name") or "-"),
        ("Channel", selected.get("channel") or "-"),
        ("Role", selected.get("role") or "-"),
        ("Current status", selected.get("attendance_status") or "-"),
    ]
    items = "".join(
        f"""
        <div>
            <div class="ssc-selected-label">{html.escape(label)}</div>
            <div class="ssc-selected-value">{html.escape(str(value))}</div>
        </div>
        """
        for label, value in fields
    )
    st.markdown(
        f"""
        <div class="ssc-selected-attendee">
            <div class="ssc-selected-name">{html.escape(str(attendee_name))}</div>
            <div class="ssc-selected-attendee-grid">{items}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def missing_contact_fields(selected):
    missing = []
    if not _field_filled(selected.get("email")):
        missing.append("email address")
    if not _field_filled(selected.get("phone_number")):
        missing.append("phone number")
    return missing


def render_required_contact_followup(selected):
    missing = missing_contact_fields(selected)
    if not missing:
        return

    st.markdown(
        f"""
        <div class="ssc-contact-warning">
            Required contact info missing: {html.escape(" and ".join(missing))}. You can add it manually now, then ask the attendee to complete the full profile later.
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Manually add required contact info", expanded=False):
        with st.form(f"manual_contact_{selected['registration_id']}_{selected['participant_id']}", clear_on_submit=True):
            email = st.text_input("Email address", value=selected.get("email") or "")
            phone = st.text_input("Phone number", value=selected.get("phone_number") or "")
            submitted = st.form_submit_button("Save contact info", type="primary", use_container_width=True)
        if submitted:
            changes = {}
            if email.strip():
                changes["email"] = email.strip().lower()
            if phone.strip():
                changes["phone_number"] = phone.strip()
            if not changes:
                st.error("Add at least an email address or phone number.")
            else:
                repo.update_participant(selected["participant_id"], changes)
                st.success("Contact info updated in the current database.")
                st.rerun()
                st.rerun()


PROFILE_COMPLETION_FIELDS = [
    ("email", "Email"),
    ("phone_number", "Phone"),
    ("address", "Address"),
    ("city", "City"),
    ("country", "Country"),
    ("dob", "Date of birth"),
    ("whatsapp_groupchat", "WhatsApp groupchat"),
    ("have_connect", "Connect account"),
    ("marketing_subs", "Marketing subscription"),
]


def _field_filled(value):
    if value is None or pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def profile_completion_status(row):
    filled = sum(1 for field, _ in PROFILE_COMPLETION_FIELDS if _field_filled(row.get(field)))
    total = len(PROFILE_COMPLETION_FIELDS)
    score = filled / total if total else 1
    missing = [label for field, label in PROFILE_COMPLETION_FIELDS if not _field_filled(row.get(field))]
    missing_contact = not (_field_filled(row.get("email")) or _field_filled(row.get("phone_number")))
    return score, missing, missing_contact


PROFILE_FIELD_LABELS = dict(PROFILE_COMPLETION_FIELDS)
PROFILE_FIELD_LABELS["participant_name"] = "Name"


def render_profile_sync_result(result):
    source = result.get("source") or "profile responses"
    st.success(
        f"Synced {source}: updated {result['updated']} participant profile(s), "
        f"found {result.get('unchanged', 0)} unchanged row(s), and skipped "
        f"{result['skipped']} row(s)."
    )
    if result.get("errors"):
        with st.expander("Skipped response details", expanded=False):
            for item in result["errors"]:
                st.warning(f"Row {item.get('row', '-')}: {item.get('reason', 'Skipped')}")


def should_show_profile_qr(row, threshold):
    score, _, missing_contact = profile_completion_status(row)
    return missing_contact or score < threshold


def profile_form_template():
    return st.session_state.get("profile_form_template", "").strip()


def build_profile_form_url(row, current_event=None):
    template = profile_form_template()
    if not template:
        return google_forms.build_profile_completion_url(row, event=current_event)
    values = {
        "event_id": row.get("event_id") or (current_event or {}).get("event_id") or "",
        "event_name": row.get("event_name") or (current_event or {}).get("event_name") or "",
        "registration_id": row.get("registration_id") or "",
        "participant_id": row.get("participant_id") or "",
        "participant_name": row.get("participant_name") or "",
        "email": row.get("email") or "",
        "phone_number": row.get("phone_number") or "",
        "country": row.get("country") or "",
        "notes": row.get("notes") or "",
    }
    url = template
    for key, value in values.items():
        url = url.replace("{" + key + "}", quote_plus(str(value)))
    return url


def qr_png_bytes(url):
    if qrcode is None or not url:
        return None
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#c61770", back_color="white").convert("RGB")
    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def qr_fallback_image_url(url, size=260):
    if not url:
        return None
    params = urlencode({"text": url, "size": str(size), "margin": "2"})
    return f"https://quickchart.io/qr?{params}"


def safe_qr_filename(row):
    name = re.sub(r"[^A-Za-z0-9]+", "_", str(row.get("participant_name") or "")).strip("_")
    name = name[:45] or "attendee"
    return f"{row.get('registration_id')}_{row.get('participant_id')}_{name}.png"


def qr_font(size, bold=False):
    if ImageFont is None:
        return None
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_centered(draw, text, y, font, fill, width):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + (bbox[3] - bbox[1])


def qr_card_png_bytes(payload):
    png = qr_png_bytes(payload.get("url"))
    if not png:
        return None
    if Image is None or ImageDraw is None:
        return png

    qr_img = Image.open(BytesIO(png)).convert("RGB").resize((540, 540))
    width = 760
    missing_lines = textwrap.wrap("Missing: " + ", ".join(payload.get("missing") or []), width=58)[:3]
    height = 760 + (len(missing_lines) * 24)
    card = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(card)
    title_font = qr_font(28, bold=True)
    subtitle_font = qr_font(22)
    small_font = qr_font(18)

    y = 26
    y = draw_centered(draw, "SSC Profile Completion", y, title_font, "#c61770", width) + 10
    y = draw_centered(
        draw,
        f"{payload.get('registration_id')} | {payload.get('participant_id')}",
        y,
        subtitle_font,
        "#111111",
        width,
    ) + 6
    name = str(payload.get("participant_name") or "")
    if len(name) > 42:
        name = name[:39] + "..."
    y = draw_centered(draw, name, y, subtitle_font, "#111111", width) + 14
    card.paste(qr_img, ((width - 540) // 2, y))
    y += 558
    y = draw_centered(draw, f"Profile completeness: {payload.get('score', 0):.0%}", y, small_font, "#111111", width) + 8
    for line in missing_lines:
        y = draw_centered(draw, line, y, small_font, "#111111", width) + 4
    draw_centered(draw, "Scan to complete the Google Form", y + 5, small_font, "#c61770", width)

    output = BytesIO()
    card.save(output, format="PNG")
    return output.getvalue()


def profile_qr_zip_bytes(rows, threshold, current_event):
    if qrcode is None:
        return None

    output = BytesIO()
    index_rows = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            payload = profile_qr_payload(row, threshold, current_event)
            if not payload:
                continue
            png = qr_card_png_bytes(payload)
            if not png:
                continue
            filename = safe_qr_filename(row)
            zf.writestr(filename, png)
            index_rows.append({
                "file_name": filename,
                "registration_id": row.get("registration_id"),
                "participant_id": row.get("participant_id"),
                "participant_name": row.get("participant_name"),
                "event_id": current_event.get("event_id"),
                "event_name": current_event.get("event_name"),
                "profile_completeness": f"{payload['score']:.0%}",
                "missing_fields": ", ".join(payload.get("missing") or []),
                "prefilled_form_url": payload.get("url"),
            })

        fieldnames = [
            "file_name", "registration_id", "participant_id", "participant_name",
            "event_id", "event_name", "profile_completeness", "missing_fields",
            "prefilled_form_url",
        ]
        csv_string = []
        csv_string.append(",".join(fieldnames))
        for item in index_rows:
            row_output = BytesIO()
            row_text = []
            for field in fieldnames:
                value = str(item.get(field) or "").replace('"', '""')
                row_text.append(f'"{value}"')
            csv_string.append(",".join(row_text))
        zf.writestr("index.csv", "\n".join(csv_string))

    return output.getvalue()


def profile_qr_payload(row, threshold, current_event):
    score, missing, missing_contact = profile_completion_status(row)
    if not should_show_profile_qr(row, threshold):
        return None
    return {
        "event_id": current_event.get("event_id"),
        "registration_id": row.get("registration_id"),
        "participant_id": row.get("participant_id"),
        "participant_name": row.get("participant_name"),
        "score": score,
        "missing": missing,
        "missing_contact": missing_contact,
        "url": build_profile_form_url(row, current_event=current_event),
    }


def render_profile_qr(payload):
    if not payload:
        return
    st.markdown("#### Complete Your SSC Profile!")
    if not payload.get("url"):
        st.info("Add a Google Form pre-filled link template in the Profile Completion tab to show the QR code.")
        return
    png = qr_png_bytes(payload["url"])
    if png:
        st.image(png, width=220)
    else:
        fallback_url = qr_fallback_image_url(payload["url"])
        if fallback_url:
            st.image(fallback_url, width=260)
        else:
            st.info("QR package is not installed yet. The direct Google Form link is shown below.")
    st.link_button("Open complete-profile form", payload["url"], use_container_width=True)


def profile_completion_tab(current_event, attendee_rows):
    event_id = current_event["event_id"]
    colored_heading("Profile Completion", PINK)
    st.caption(
        "One profile table for every participant in this event. Sync from Google Sheets "
        "or upload a CSV/Excel export when needed."
    )
    sync_result = st.session_state.pop(f"profile_sync_result_{event_id}", None)
    worksheet_name = str(event_id)
    google_configured = google_forms.is_configured(st.secrets)
    upload_version_key = f"profile_upload_version_{event_id}"
    upload_version = st.session_state.get(upload_version_key, 0)

    title_col, sync_col, upload_col = st.columns([6, 1, 1])
    with title_col:
        st.markdown("#### Participant Profiles")
    with sync_col:
        sync_clicked = st.button(
            "Sync",
            type="primary",
            key=f"sync_google_profiles_{event_id}",
            disabled=not google_configured,
            help=f"Sync worksheet {worksheet_name}",
        )
    with upload_col:
        with st.popover("Upload"):
            uploaded = st.file_uploader(
                "CSV or Excel file",
                type=["csv", "xlsx"],
                key=f"profile_upload_{event_id}_{upload_version}",
                label_visibility="collapsed",
            )
            apply_upload = st.button(
                "Apply upload",
                type="primary",
                disabled=uploaded is None,
                key=f"apply_profile_upload_{event_id}_{upload_version}",
            )

    if sync_clicked:
        try:
            sheet_df = google_forms.load_profile_completion_responses(
                st.secrets,
                worksheet_name=worksheet_name,
            )
            if sheet_df.empty:
                st.warning(f"Worksheet {worksheet_name} has no response rows.")
            else:
                result = repo.import_profile_completion_responses(
                    sheet_df.to_dict("records"),
                    event_id=event_id,
                )
                result["source"] = f"worksheet {worksheet_name}"
                st.session_state[f"profile_sync_result_{event_id}"] = result
                st.rerun()
        except Exception as exc:
            st.error(f"Could not sync worksheet {worksheet_name}: {exc}")

    if apply_upload and uploaded is not None:
        try:
            if uploaded.name.lower().endswith(".csv"):
                upload_df = pd.read_csv(uploaded, dtype=str, keep_default_na=False)
            else:
                upload_df = pd.read_excel(uploaded, dtype=str, keep_default_na=False)
            if upload_df.empty:
                st.warning("The uploaded file has no response rows.")
            else:
                result = repo.import_profile_completion_responses(
                    upload_df.to_dict("records"),
                    event_id=event_id,
                )
                result["source"] = "uploaded profile sheet"
                st.session_state[f"profile_sync_result_{event_id}"] = result
                st.session_state[upload_version_key] = upload_version + 1
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read or apply the uploaded file: {exc}")

    if not google_configured:
        st.caption("Google Sheet access is not configured yet; Upload remains available.")
    if sync_result:
        render_profile_sync_result(sync_result)

    changes_by_participant = {
        str(change["participant_id"]): change
        for change in (sync_result or {}).get("changes", [])
    }
    unique_participants = {}
    for row in attendee_rows:
        unique_participants.setdefault(str(row.get("participant_id")), row)

    profile_rows = []
    for row in unique_participants.values():
        participant_id = str(row.get("participant_id") or "")
        score, missing, _ = profile_completion_status(row)
        change = changes_by_participant.get(participant_id)
        before_score = profile_completion_status(change["before"])[0] if change else None
        updated_fields = (
            ", ".join(
                PROFILE_FIELD_LABELS.get(field, field.replace("_", " ").title())
                for field in change.get("updated_fields", [])
            )
            if change
            else "-"
        )
        profile_rows.append({
            "Registration code": row.get("registration_id") or "-",
            "Participant ID": participant_id,
            "Name": row.get("participant_name") or "-",
            "Email": row.get("email") or "-",
            "Phone": str(row.get("phone_number")) if row.get("phone_number") else "-",
            "Address": row.get("address") or "-",
            "City": row.get("city") or "-",
            "Country": row.get("country") or "-",
            "Birthday": row.get("dob") or "-",
            "WhatsApp group": repo.db_to_bool_label(row.get("whatsapp_groupchat")),
            "Connect account": repo.db_to_bool_label(row.get("have_connect")),
            "Marketing subscription": repo.db_to_bool_label(row.get("marketing_subs")),
            "Previous profile %": f"{before_score:.0%}" if before_score is not None else "-",
            "Profile completeness": f"{score:.0%}",
            "Change": f"{score - before_score:+.0%}" if before_score is not None else "-",
            "Updated fields": updated_fields,
            "Missing fields": ", ".join(missing) or "-",
        })

    if profile_rows:
        st.dataframe(pd.DataFrame(profile_rows), hide_index=True, use_container_width=True)
    else:
        st.info("No attendees found for this event.")


events = repo.events_with_stats()
if not events:
    st.info("Create an event first.")
    st.stop()

event_options = {f"{row['event_id']} — {row['event_name']} ({row['start_datetime']})": row for row in events}
event_labels = list(event_options)
stored_event_id = st.session_state.get("selected_event_id")
default_event_index = 0
if stored_event_id is not None:
    for index, label in enumerate(event_labels):
        if int(event_options[label]["event_id"]) == int(stored_event_id):
            default_event_index = index
            break
selected_event = event_options[st.selectbox("Event Selection", event_labels, index=default_event_index)]
event_id = selected_event["event_id"]
st.session_state["selected_event_id"] = int(event_id)

st.markdown(
    f"<h2 style='color:{PRIMARY}; margin-bottom:.4rem;'>{selected_event['event_name']}</h2>",
    unsafe_allow_html=True,
)

info_cols = st.columns(4)
with info_cols[0]:
    basic_info("Location", selected_event.get("location_name") or "-")
with info_cols[1]:
    basic_info("Date", selected_event.get("start_datetime") or "-")
with info_cols[2]:
    basic_info("Type", selected_event.get("etype_name") or "-")
with info_cols[3]:
    basic_info("Price", f"€{float(selected_event.get('ticket_cost') or 0):.2f}")

st.markdown("<div style='height:1.1rem;'></div>", unsafe_allow_html=True)

tab_registration, tab_checkin, tab_attendees, tab_profile, tab_post = st.tabs([
    "Registration",
    "Check-in",
    "Attendee List",
    "Profile Completion",
    "Post-event Dashboard",
])

with tab_registration:
    colored_heading("Registration details", PINK)
    registration_result = st.session_state.pop(f"registration_result_{event_id}", None)
    if registration_result:
        if registration_result.get("code"):
            st.success(f"Registration created. Registration code: {registration_result['code']}")
        if registration_result.get("skipped"):
            st.warning(
                "Skipped duplicate/already-registered attendee(s): "
                + ", ".join(registration_result["skipped"])
            )
    registration_version = st.session_state.get(f"registration_form_version_{event_id}", 0)
    registration_prefix = f"registration_{event_id}_{registration_version}"
    channel = st.selectbox(
        "Registration channel",
        repo.CHANNELS,
        key=f"{registration_prefix}_channel",
        accept_new_options=True,
        placeholder="Select or enter a registration channel",
    )
    channel = repo.normalize_registration_channel(channel)
    immediate_checkin = channel == "Walk-in"
    if immediate_checkin:
        st.markdown(
            "<div class='ssc-walkin-notice'>Walk-in selected: all attendees in this registration will be checked in immediately.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("#### Main Registrant")
    registration_participants = repo.participants_for_registration()
    main = participant_inputs(f"{registration_prefix}_main", registration_participants, require_contact=True)
    main_attends = st.checkbox("Main registrant will attend", value=True, key=f"{registration_prefix}_main_attends")
    render_registration_conflicts(event_id, "Main registrant", main)

    attendees = []
    if main_attends:
        need_buddy = repo.bool_to_db(st.selectbox("Main attendee needs buddy?", repo.BOOL_OPTIONS, key=f"{registration_prefix}_main_buddy"))
    else:
        st.markdown("#### Main Attendee info")
        main_attendee = participant_inputs(
            f"{registration_prefix}_main_attendee", registration_participants, require_contact=True
        )
        render_registration_conflicts(event_id, "Main attendee", main_attendee)
        need_buddy = repo.bool_to_db(st.selectbox("Main attendee needs buddy?", repo.BOOL_OPTIONS, key=f"{registration_prefix}_main_attendee_buddy"))

    guest_count = st.number_input("Number of guests", min_value=0, max_value=10, value=0, step=1, key=f"{registration_prefix}_guest_count")
    guests = []
    for index in range(int(guest_count)):
        with st.expander(f"Guest {index + 1}", expanded=True):
            guest = participant_inputs(
                f"{registration_prefix}_guest_{index}", registration_participants, require_contact=False
            )
            guest["need_buddy"] = repo.bool_to_db(st.selectbox("Guest needs buddy?", repo.BOOL_OPTIONS, key=f"{registration_prefix}_guest_{index}_buddy"))
            guests.append(guest)
            render_registration_conflicts(event_id, f"Guest {index + 1}", guest)

    current_attendees = [("Main registrant", main)] if main_attends else [("Main attendee", main_attendee)]
    current_attendees.extend(
        (f"Guest {index + 1}", guest)
        for index, guest in enumerate(guests)
        if guest.get("participant_name")
    )
    render_current_form_duplicates(current_attendees)

    notes = st.text_area("Notes for registration", key=f"{registration_prefix}_notes")
    estimated_attendees = 1 + len([guest for guest in guests if guest.get("participant_name")])
    registration_summary(channel, estimated_attendees)
    button_label = "Create registration + check-in" if immediate_checkin else "Create registration"

    if st.button(button_label, type="primary", use_container_width=True):
        try:
            validate_person(main, "Main registrant")
            main_pid, _ = repo.upsert_participant(main)
            if main_attends:
                attendees.append({
                    "participant_id": main_pid,
                    "role": "Main Attendee",
                    "need_buddy": need_buddy,
                    "label": main.get("participant_name") or main_pid,
                })
            else:
                validate_person(main_attendee, "Main attendee")
                attendee_pid, _ = repo.upsert_participant(main_attendee)
                attendees.append({
                    "participant_id": attendee_pid,
                    "role": "Main Attendee",
                    "need_buddy": need_buddy,
                    "label": main_attendee.get("participant_name") or attendee_pid,
                })
            for guest_index, guest in enumerate(guests, start=1):
                if not guest.get("participant_name"):
                    raise ValueError(f"Guest {guest_index}: name is required.")
                guest_pid, _ = repo.upsert_participant(guest)
                attendees.append({
                    "participant_id": guest_pid,
                    "role": "Guest",
                    "need_buddy": guest.get("need_buddy"),
                    "label": guest.get("participant_name") or guest_pid,
                })
            code, skipped = repo.create_registration_group(
                event_id, main_pid, attendees, channel, notes, immediate_checkin=immediate_checkin
            )
            if code:
                st.session_state[f"registration_result_{event_id}"] = {
                    "code": code,
                    "skipped": skipped,
                }
                st.session_state[f"registration_form_version_{event_id}"] = registration_version + 1
                st.rerun()
            elif skipped:
                st.warning(
                    "No registration was created because every attendee was already registered "
                    "or entered more than once: " + ", ".join(skipped)
                )
        except Exception as exc:
            st.error(str(exc))

with tab_checkin:
    colored_heading("Check-in", PINK)
    all_rows = repo.attendee_rows(event_id, include_attended=True)
    pending_rows = repo.attendee_rows(event_id, include_attended=False)
    active_registrations = [row for row in repo.registrations(event_id) if row["status"] != "Cancelled"]
    checked_rows = [row for row in all_rows if row["attendance_status"] == "Attended"]

    recent_message = st.session_state.pop(f"checkin_success_{event_id}", None)
    if recent_message:
        st.success(recent_message)

    recent_qr = st.session_state.pop(f"profile_qr_after_checkin_{event_id}", None)
    if recent_qr:
        with st.container(border=True):
            st.success(f"{recent_qr['participant_name']} checked in with code {recent_qr['registration_id']}.")
            render_profile_qr(recent_qr)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Registration", len(active_registrations))
    m2.metric("Checked-in", len(checked_rows))
    m3.metric("Remaining/Pending", len(pending_rows))

    search = st.text_input(
        "Search attendee table",
        placeholder="Registration code, name, role, registered by, email, phone, channel, status...",
    )
    matches = repo.filter_attendees(pending_rows, search)
    if not matches:
        st.info("No pending attendee matches your search.")
    else:
        table = pd.DataFrame(matches)
        display = table[[
            "registration_id", "participant_name", "role", "registered_by_name",
            "email", "phone_number", "channel", "notes", "attendance_status"
        ]].copy()
        display.columns = ["Registration code", "Name", "Role", "Registered by", "Email", "Phone", "Channel", "Status"]
        st.dataframe(display, hide_index=True, use_container_width=True)

        options = {f"{row['registration_id']} — {row['participant_name']} — {row['role']}": row for row in matches}
        selected = options[st.selectbox("Selected Attendee", options)]
        with st.container(border=True):
            threshold = float(st.session_state.get("profile_completion_threshold", 0.7))
            qr_payload = profile_qr_payload(selected, threshold, selected_event)

            info_col, action_col = st.columns([1.35, 1], gap="large")
            with info_col:
                selected_attendee_details(selected)
                render_required_contact_followup(selected)
            with action_col:
                if qr_payload:
                    render_profile_qr(qr_payload)
                else:
                    st.success("This attendee is above the selected profile-completion threshold.")
                if st.button("Check-in", type="primary", use_container_width=True):
                    changed = repo.check_in(selected["registration_id"], selected["participant_id"])
                    if changed:
                        if qr_payload:
                            st.session_state[f"profile_qr_after_checkin_{event_id}"] = qr_payload
                        else:
                            st.session_state[f"checkin_success_{event_id}"] = (
                                f"{selected['participant_name']} checked in with code {selected['registration_id']}."
                            )
                    else:
                        st.info("No row changed. This attendee may already be checked in.")
                    st.rerun()
            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

with tab_attendees:
    colored_heading("Attendee List", PINK)
    all_rows = repo.attendee_rows(event_id, include_attended=True)
    checked_rows = [row for row in all_rows if row["attendance_status"] == "Attended"]
    search = st.text_input("Search checked-in attendees", placeholder="Registration code, name, email, phone", key="checked_search")
    checked_rows = repo.filter_attendees(checked_rows, search)
    if checked_rows:
        display = pd.DataFrame(checked_rows)[[
            "registration_id", "participant_name", "role", "registered_by_name",
            "email", "phone_number", "channel", "checkin_datetime"
        ]]
        display.columns = ["Registration code", "Name", "Role", "Registered by", "Email", "Phone", "Channel", "Check-in datetime"]
        st.dataframe(display, hide_index=True, use_container_width=True)
    else:
        st.info("No checked-in attendees found.")

with tab_profile:
    all_rows = repo.attendee_rows(event_id, include_attended=True)
    profile_completion_tab(selected_event, all_rows)

with tab_post:
    colored_heading("Post-event Dashboard", PINK)
    all_rows = repo.attendee_rows(event_id, include_attended=True)
    df = pd.DataFrame(all_rows)
    registered = len(all_rows)
    checked = int((df["attendance_status"] == "Attended").sum()) if not df.empty else 0
    no_show = int((df["attendance_status"] == "No Show").sum()) if not df.empty else 0
    pending = int((df["attendance_status"] == "Not Checked In").sum()) if not df.empty else 0
    attendance_rate = checked / registered if registered else 0

    st.subheader("Close Event")
    if pending:
        st.warning(f"{pending} attendee(s) are still pending.")
    confirm = st.checkbox("I confirm the event is finished and pending attendees should be marked as No Show")
    if st.button("Mark all pending attendees as No Show", disabled=not confirm, type="primary", use_container_width=True):
        changed = repo.mark_remaining_no_show(event_id)
        st.success(f"Marked {changed} attendee(s) as No Show.")
        st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered", registered)
    c2.metric("Check-in", checked)
    c3.metric("No Show", no_show)
    c4.metric("Attendance Rate", f"{attendance_rate:.0%}")

    st.subheader("Post-event Feedback")
    feedback_url = google_forms.build_post_event_feedback_url(selected_event)
    with st.container(border=True):
        qr_col, feedback_col = st.columns([1, 2])
        with qr_col:
            feedback_qr = qr_png_bytes(feedback_url)
            if feedback_qr:
                st.image(feedback_qr, width=220)
            else:
                fallback_url = qr_fallback_image_url(feedback_url)
                if fallback_url:
                    st.image(fallback_url, width=240)
        with feedback_col:
            st.markdown("#### Share the event feedback form")
            st.write(
                "Participants can scan this QR code to open the feedback form. "
                f"Event {event_id} and the event name are pre-filled automatically."
            )
            st.link_button("Open feedback form", feedback_url)

    if df.empty:
        st.info("No attendee data yet.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Attendees by type")
            st.bar_chart(df["registration_type"].fillna("Unknown").value_counts())
        with c2:
            st.subheader("Attendees by channel")
            st.bar_chart(df["channel"].fillna("Unknown").value_counts())
