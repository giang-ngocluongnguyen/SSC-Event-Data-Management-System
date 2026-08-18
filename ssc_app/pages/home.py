import streamlit as st

import repository as repo
from layout import colored_heading, event_card, page_header


page_header(
    "Special Social Event",
    "Home",
    "Overview of past SSC events, registrations, attendance, and upcoming activities.",
)

kpis = repo.home_past_kpis()
rate = f"{kpis['attendance_rate']:.0%}" if kpis["attendance_rate"] else "0%"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total events", int(kpis.get("total_events") or 0))
c2.metric("Total participants", int(kpis.get("total_participants") or 0))
c3.metric("Total registrations", int(kpis.get("total_registrations") or 0))
c4.metric("% attended", rate)

past, upcoming = repo.split_events_for_home()


colored_heading("Upcoming Events")
if not upcoming:
    st.caption("No upcoming events found.")
else:
    cols = st.columns(3)
    for index, row in enumerate(upcoming):
        with cols[index % 3]:
            event_card(row, past=False)

colored_heading("Past Events")
if not past:
    st.caption("No past events found.")
else:
    cols = st.columns(3)
    for index, row in enumerate(past):
        with cols[index % 3]:
            event_card(row, past=True)

st.divider()
with st.expander("Image for Event Card", expanded=False):
    events = repo.events_with_stats(include_archived=True)
    if not events:
        st.info("No events found.")
    else:
        uploader_version = st.session_state.get("event_card_image_uploader_version", 0)
        event_options = {f"{row['event_id']} — {row['event_name']}": row for row in events}
        selected = event_options[st.selectbox("Choose event", event_options, key="event_card_image_event")]
        uploaded = st.file_uploader(
            "Image for Event Card",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"event_card_image_upload_{uploader_version}",
        )
        if st.button("Save event image", type="primary", disabled=uploaded is None):
            repo.save_event_image(selected["event_id"], uploaded)
            st.session_state["event_card_image_uploader_version"] = uploader_version + 1
            st.success("Event image saved.")
            st.rerun()
