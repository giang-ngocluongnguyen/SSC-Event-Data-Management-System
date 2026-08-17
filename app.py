import streamlit as st

from database import initialize_database
from layout import sidebar_footer, sidebar_header, sidebar_navigation, setup_page


setup_page()
initialize_database()
sidebar_header()

navigation = st.navigation(
    {
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
    },
    position="hidden",
)
sidebar_navigation()
sidebar_footer()
navigation.run()
