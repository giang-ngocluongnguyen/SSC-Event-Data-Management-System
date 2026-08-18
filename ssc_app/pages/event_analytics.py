from io import BytesIO
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from google_forms import build_post_event_feedback_url
from layout import PINK, colored_heading, page_header
import repository as repo

try:
    import qrcode
except ImportError:
    qrcode = None


page_header(
    "Event Management",
    "Event Analytics",
    "Post-event feedback, attendance analytics, and reporting.",
)

events = pd.DataFrame(repo.events_with_stats(include_archived=True))
if events.empty:
    st.info("No event data available.")
    st.stop()

events["attendance_rate"] = events.apply(
    lambda row: row["attended_count"] / row["attendee_count"] if row["attendee_count"] else 0,
    axis=1,
)


def qr_png_bytes(url):
    if qrcode is None or not url:
        return None
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#c61770", back_color="white")
    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def qr_fallback_image_url(url, size=260):
    if not url:
        return None
    params = urlencode({"text": url, "size": str(size), "margin": "2"})
    return f"https://quickchart.io/qr?{params}"


def read_feedback_upload(uploaded):
    if uploaded.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded)
    return pd.read_excel(uploaded)


def render_feedback_summary(df):
    st.metric("Feedback responses", len(df))
    numeric = df.select_dtypes(include="number")
    if not numeric.empty:
        averages = numeric.mean().round(2).reset_index()
        averages.columns = ["Question", "Average score"]
        st.dataframe(averages, hide_index=True, use_container_width=True)


colored_heading("Post-event Feedback", PINK)
event_options = {
    f"{int(row['event_id'])} — {row['event_name']}": row.to_dict()
    for _, row in events.iterrows()
}
selected_event = event_options[st.selectbox("Feedback Event", list(event_options))]
feedback_url = build_post_event_feedback_url(selected_event)

with st.container(border=True):
    qr_col, upload_col = st.columns([0.9, 1.25], gap="large")
    with qr_col:
        st.markdown("#### Feedback QR")
        st.caption("Each selected event gets its own prefilled feedback form link.")
        png = qr_png_bytes(feedback_url)
        if png:
            st.image(png, width=220)
        else:
            fallback_url = qr_fallback_image_url(feedback_url)
            if fallback_url:
                st.image(fallback_url, width=260)
            else:
                st.info("QR package is not installed yet. The direct Google Form link is shown below.")
        st.link_button("Open feedback form", feedback_url, use_container_width=True)

    with upload_col:
        st.markdown("#### Upload Completed Feedback")
        st.caption("Upload the Google Sheet export for this event to preview feedback analytics in the demo.")
        upload_version_key = f"feedback_upload_version_{selected_event['event_id']}"
        upload_version = st.session_state.get(upload_version_key, 0)
        uploaded = st.file_uploader(
            "Upload completed feedback sheet",
            type=["csv", "xlsx"],
            key=f"feedback_upload_{selected_event['event_id']}_{upload_version}",
        )
        if uploaded is not None:
            try:
                feedback_df = read_feedback_upload(uploaded)
            except Exception as exc:
                st.error(f"Could not read uploaded file: {exc}")
            else:
                if feedback_df.empty:
                    st.warning("The uploaded feedback sheet has no rows.")
                else:
                    render_feedback_summary(feedback_df)
                    st.dataframe(feedback_df.head(30), hide_index=True, use_container_width=True)
                    if st.button("Clear uploaded feedback", use_container_width=True):
                        st.session_state[upload_version_key] = upload_version + 1
                        st.rerun()

st.divider()

colored_heading("Post-event Dashboard", PINK)
display = events[[
    "event_id", "event_name", "start_datetime", "location_name", "etype_name",
    "partner_name", "registration_count", "attendee_count", "attended_count",
    "pending_count", "no_show_count", "attendance_rate"
]].copy()
display.columns = [
    "Event ID", "Event", "Start", "Location", "Type", "Partner",
    "Registrations", "Attendees", "Attended", "Pending", "No Show", "Attendance rate"
]
st.dataframe(display, hide_index=True, use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Attendance by event")
    chart = display.set_index("Event")[["Attended", "Pending", "No Show"]]
    st.bar_chart(chart)
with c2:
    st.subheader("Registrations by event type")
    st.bar_chart(display.groupby("Type")["Registrations"].sum())
