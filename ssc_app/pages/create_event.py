from datetime import date, datetime, time

import streamlit as st

import repository as repo
from layout import PRIMARY, colored_heading, page_header


ACCESSIBILITY_OPTIONS = [
    "Automatische deuren",
    "Lage bar",
    "Lift",
    "MIVA Toilet",
    "Prikkelarme ruimte(s)",
    "Rolstoeltoegankelijke in/uitgang",
]


page_header(
    "Event Management",
    "Create Event",
    "Create a new event and add supporting location/type records only when needed.",
)

colored_heading("Create New Event", PRIMARY)

with st.expander("Need a new location?", expanded=False):
    with st.form("new_location", clear_on_submit=True):
        location_name = st.text_input("Location name *")
        street_number = st.text_input("Street + number *")
        c1, c2, c3 = st.columns(3)
        postal_code = c1.text_input("Postal code")
        city = c2.text_input("City")
        country = c3.text_input("Country", value="NL")
        if st.form_submit_button("Add location", use_container_width=True, type="primary"):
            if not location_name or not street_number:
                st.error("Location name and street number are required.")
            else:
                location_id = repo.create_location({
                    "location_name": location_name,
                    "street_number": street_number,
                    "postal_code": postal_code,
                    "city": city,
                    "country": country,
                })
                st.success(f"Added location {location_id}.")
                st.rerun()

with st.expander("Need a new event type?", expanded=False):
    with st.form("new_event_type", clear_on_submit=True):
        type_name = st.text_input("Event type name *")
        st.caption("The ID is generated from the name, e.g. Uitgaansfeest -> UIT, Vraag Maar Raak -> VMR.")
        if st.form_submit_button("Add event type", use_container_width=True, type="primary"):
            if not type_name:
                st.error("Event type name is required.")
            else:
                etype_id = repo.create_event_type(type_name)
                st.success(f"Added event type {etype_id}.")
                st.rerun()

with st.expander("Need a new partner?", expanded=False):
    with st.form("new_partner", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            partner_name = st.text_input("Partner name *")
            partner_type = st.text_input("Partner type")
            partner_street = st.text_input("Street + number")
            partner_postal = st.text_input("Postal code")
            partner_city = st.text_input("City")
            partner_country = st.text_input("Country", value="NL")
        with c2:
            contact_person = st.text_input("Contact person *")
            partner_phone = st.text_input("Phone number")
            partner_email = st.text_input("Email address")
            partner_website = st.text_input("Website")
            partner_status = st.selectbox("Status", repo.PARTNER_STATUSES)
            partner_since = st.number_input(
                "Partner since (year)", min_value=1900, max_value=date.today().year,
                value=date.today().year, step=1,
            )
        if st.form_submit_button("Add partner", use_container_width=True, type="primary"):
            if not partner_name.strip():
                st.error("Partner name is required.")
            elif not contact_person.strip():
                st.error("Contact person's details are required.")
            else:
                partner_id = repo.create_partner({
                    "partner_name": partner_name,
                    "partner_type": partner_type,
                    "street_number": partner_street,
                    "postal_code": partner_postal,
                    "city": partner_city,
                    "country": partner_country,
                    "contact_person": contact_person,
                    "phone_number": partner_phone,
                    "email_address": partner_email.strip().lower(),
                    "website": partner_website,
                    "status": partner_status,
                    "partner_since": int(partner_since),
                })
                st.success(f"Added partner {partner_id}.")
                st.rerun()

colored_heading("New Event Details", PRIMARY)
locations = repo.locations()
types = repo.event_types()
partners = repo.active_partners() or repo.partners()

if not locations or not types or not partners:
    st.warning("You need at least one active location, event type, and partner before creating events.")
else:
    st.caption(f"Next event_id: {repo.next_event_id_preview()}")
    with st.form("create_event", clear_on_submit=True):
        event_name = st.text_input("Event name *")
        loc_options = {f"{row['location_id']} — {row['location_name']}": row for row in locations}
        type_options = {f"{row['etype_id']} — {row['etype_name']}": row for row in types}
        partner_options = {f"{row['partner_id']} — {row['partner_name']}": row for row in partners}
        selected_location = loc_options[st.selectbox("Location *", loc_options)]
        selected_type = type_options[st.selectbox("Event type *", type_options)]
        selected_partner = partner_options[st.selectbox("Partner *", partner_options)]
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start date")
        start_time = c1.time_input("Start time", value=time(18, 0))
        end_date = c2.date_input("End date")
        end_time = c2.time_input("End time", value=time(20, 0))
        c3, c4 = st.columns(2)
        age_rating = c3.selectbox("Age rating", ["18+", "12-18", "Everyone"])
        ticket_cost = c4.number_input("Ticket cost", min_value=0.0, value=0.0, step=1.0)
        st.markdown("**Accessibility**")
        accessibility_cols = st.columns(2)
        selected_accessibility = []
        for index, option in enumerate(ACCESSIBILITY_OPTIONS):
            with accessibility_cols[index % 2]:
                if st.checkbox(option, key=f"accessibility_{index}"):
                    selected_accessibility.append(option)
        event_image = st.file_uploader("Event image for card", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Create event", use_container_width=True, type="primary")
    if submitted:
        if not event_name:
            st.error("Event name is required.")
        else:
            event_id = repo.create_event({
                "location_id": selected_location["location_id"],
                "event_type": selected_type["etype_id"],
                "partner_id": selected_partner["partner_id"],
                "event_name": event_name,
                "start_datetime": datetime.combine(start_date, start_time).strftime("%Y-%m-%d %H:%M"),
                "end_datetime": datetime.combine(end_date, end_time).strftime("%Y-%m-%d %H:%M"),
                "age_rating": age_rating,
                "ticket_cost": ticket_cost,
                "accessibility": ", ".join(selected_accessibility),
            })
            if event_image is not None:
                repo.save_event_image(event_id, event_image)
            st.success(f"Created event #{event_id}.")
            st.rerun()
