import streamlit as st

from auth import require_login
from database import initialize_database
from layout import sidebar_footer, sidebar_header, sidebar_navigation, setup_page


setup_page()
if not require_login():
    st.stop()

initialize_database()
sidebar_header()

role = st.session_state.get("role", "volunteer")

pages = {
    "OVERVIEW": [
        st.Page("pages/home.py", title="Home", icon="🏠"),
    ],
    "EVENT MANAGEMENT": [
        st.Page("pages/event_workspace.py", title="Event Workspace", icon="🎟️"),
    ],
}

if role == "admin":
    pages = {
        "OVERVIEW": [
            st.Page("pages/home.py", title="Home", icon="🏠"),
        ],
        "EVENT MANAGEMENT": [
            st.Page("pages/create_event.py", title="Create Event", icon="➕"),
            st.Page("pages/event_workspace.py", title="Event Workspace", icon="🎟️"),
            st.Page("pages/event_analytics.py", title="Event Analytics", icon="📊"),
        ],
        "DATA MANAGEMENT": [
            st.Page("pages/database.py", title="Database", icon="🗄️"),
            st.Page("pages/audit_log.py", title="Audit Log", icon="🧾"),
        ],
    }

navigation = st.navigation(pages, position="hidden")
sidebar_navigation(role)
sidebar_footer()
navigation.run()
