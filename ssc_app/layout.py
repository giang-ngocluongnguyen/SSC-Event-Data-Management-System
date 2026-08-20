from pathlib import Path
import base64
import html
import math
import mimetypes

import streamlit as st


APP_TITLE = "Special Social Event Hub"
SIDEBAR_TITLE = "The Special Social Club"
ASSET_DIR = Path(__file__).parent / "assets"
PRIMARY = "#c61770"
BLACK = "#000000"
WHITE = "#ffffff"
TEAL = "#12a19c"
PINK = "#f6b8cf"
CARD = "rgba(18, 161, 156, 0.70)"


def _first_existing(names):
    for name in names:
        path = ASSET_DIR / name
        if path.exists():
            return path
    return None


def setup_page():
    st.set_page_config(page_title=APP_TITLE, page_icon="🎟️", layout="wide")
    st.markdown(
        f"""
        <style>
        .block-container {{
            padding-top: 1rem;
            padding-bottom: 1.8rem;
        }}
        :root {{
            --ssc-dark-text: #2f3138;
            --ssc-muted-text: #4f5360;
        }}
        h1, h2, h3, h4 {{
            margin-top: 0.65rem;
            margin-bottom: 0.45rem;
        }}
        [data-testid="stMarkdownContainer"] hr {{
            margin: 0.55rem 0 0.95rem 0;
        }}
        div[data-testid="stExpander"] {{
            margin: 0.35rem 0 0.65rem 0;
        }}
        div[data-testid="stForm"] {{
            margin-top: 0.25rem;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.85rem;
            margin-top: 0.45rem;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
            padding-top: 0.75rem;
        }}
        [data-testid="stSidebar"] {{
            background-color: {PINK};
        }}
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {{
            color: var(--ssc-dark-text) !important;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label {{
            color: var(--ssc-dark-text) !important;
        }}
        [data-testid="stSidebar"] a,
        [data-testid="stSidebar"] a span,
        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"],
        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span {{
            color: var(--ssc-dark-text) !important;
        }}
        [data-baseweb="select"] > div {{
            background-color: rgba(246, 184, 207, 0.35);
            border-color: {PINK};
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] [data-baseweb="select"] span {{
            color: var(--ssc-dark-text) !important;
        }}
        .ssc-app-name {{
            color: var(--ssc-dark-text) !important;
            font-weight: 800;
            font-size: 1.28rem;
            line-height: 1.2;
            padding: 0.15rem 0 0.1rem 0;
            margin: 0.25rem 0 0.1rem 0;
        }}
        .ssc-app-description {{
            color: var(--ssc-muted-text) !important;
            opacity: 0.72;
            font-size: 0.9rem;
            line-height: 1.3;
            margin: 0 0 0.55rem 0;
        }}
        .ssc-sidebar-divider {{
            border: none;
            border-top: 1px solid rgba(255, 255, 255, 0.55);
            margin: 0.5rem 0 0.75rem 0;
        }}
        .ssc-sidebar-group {{
            color: var(--ssc-dark-text) !important;
            font-weight: 850;
            font-size: 0.82rem;
            letter-spacing: 0.03em;
            margin: 0.95rem 0 0.25rem 0;
            text-transform: uppercase;
        }}
        .ssc-club-footer {{
            color: {PRIMARY} !important;
            font-weight: 800;
            font-size: 1.04rem;
            margin: 0.7rem 0 0.35rem 0;
        }}
        .ssc-page-title {{
            color: {PRIMARY};
            margin: 0 0 0.35rem 0;
            line-height: 1.18;
        }}
        .ssc-page-meta {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin: 0.05rem 0 0.45rem 0;
        }}
        .ssc-page-pill {{
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid rgba(18, 161, 156, 0.35);
            background: rgba(18, 161, 156, 0.08);
            color: {TEAL};
            font-weight: 800;
            padding: 0.28rem 0.72rem;
            line-height: 1.2;
        }}
        .ssc-page-description {{
            color: var(--ssc-muted-text) !important;
            opacity: 0.82;
            line-height: 1.35;
        }}
        .ssc-section-title {{
            color: {PRIMARY};
            font-weight: 700;
            margin: 0.95rem 0 0.45rem 0;
        }}
        .ssc-pink-text {{
            color: {PINK};
            font-weight: 700;
        }}
        .ssc-walkin-notice {{
            background: rgba(18, 161, 156, 0.14);
            border: 1px solid rgba(18, 161, 156, 0.45);
            border-left: 5px solid {TEAL};
            border-radius: 10px;
            color: {TEAL};
            font-weight: 800;
            padding: 0.72rem 0.9rem;
            margin: 0.45rem 0 0.75rem 0;
        }}
        .ssc-muted {{opacity: 0.75; font-size: 0.92rem;}}
        .ssc-event-card {{
            border: 1px solid rgba(0, 0, 0, 0.10);
            border-radius: 14px;
            padding: 1rem;
            background: {CARD};
            backdrop-filter: saturate(110%);
            color: {WHITE};
            min-height: 365px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .ssc-event-card * {{
            color: {WHITE};
        }}
        .ssc-event-image,
        .ssc-event-image img {{
            width: 100%;
            height: 150px;
            border-radius: 14px;
            object-fit: cover;
        }}
        .ssc-event-image {{
            margin-bottom: 0.85rem;
            background: rgba(255, 255, 255, 0.22);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.2rem;
        }}
        .ssc-event-title {{
            margin-bottom: .25rem;
            min-height: 2.8rem;
            max-height: 4.2rem;
            overflow: hidden;
        }}
        .ssc-event-info-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.42rem;
            font-size: 0.93rem;
            line-height: 1.28;
        }}
        .ssc-event-info-label {{
            font-weight: 800;
            opacity: 0.9;
        }}
        .ssc-event-divider {{
            border: none;
            border-top: 1px solid rgba(255, 255, 255, 0.45);
            margin: 0.8rem 0;
        }}
        .ssc-basic-info {{
            border: 1px solid rgba(198, 23, 112, 0.16);
            border-radius: 12px;
            padding: 0.7rem 0.8rem;
            min-height: 74px;
            background: rgba(246, 184, 207, 0.13);
        }}
        .ssc-basic-info-label {{
            font-size: 0.82rem;
            color: {PRIMARY};
            margin-bottom: 0.25rem;
        }}
        .ssc-basic-info-value {{
            font-size: 0.98rem;
            font-weight: 600;
        }}
        .ssc-selected-attendee {{
            border: 1px solid rgba(198, 23, 112, 0.16);
            border-radius: 12px;
            padding: 0.95rem 1.25rem 1.1rem 1.25rem;
            background: rgba(246, 184, 207, 0.12);
            margin: 0 0 0.4rem 0;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }}
        .ssc-selected-name {{
            color: {PRIMARY};
            font-size: 1.45rem;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 1.15rem;
            width: 100%;
            overflow-wrap: anywhere;
        }}
        .ssc-selected-attendee-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1.15rem 1.5rem;
            width: 100%;
        }}
        .ssc-selected-label {{
            color: {PRIMARY};
            font-size: 0.9rem;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 0.32rem;
        }}
        .ssc-selected-value {{
            font-size: 1.13rem;
            font-weight: 700;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }}
        .ssc-contact-warning {{
            background: rgba(18, 161, 156, 0.12);
            border: 1px solid rgba(18, 161, 156, 0.38);
            border-radius: 10px;
            color: var(--text-color);
            font-size: 0.92rem;
            font-weight: 650;
            line-height: 1.35;
            margin: 0.65rem 0 0.45rem 0;
            padding: 0.65rem 0.78rem;
        }}
        @media (max-width: 900px) {{
            .ssc-selected-attendee-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"] {{
            background-color: {PRIMARY};
            border-color: {PRIMARY};
            color: {WHITE};
        }}
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button[kind="primary"]:hover {{
            background-color: {TEAL};
            border-color: {TEAL};
            color: {WHITE};
        }}
        .stButton > button[kind="secondary"],
        .stFormSubmitButton > button[kind="secondary"] {{
            background-color: #d32f2f;
            border-color: #d32f2f;
            color: {WHITE};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    background = _first_existing(["ssc_background.png", "ssc_background.jpg", "background.png", "background.jpg"])
    if background:
        mime = mimetypes.guess_type(background.name)[0] or "image/png"
        encoded = base64.b64encode(background.read_bytes()).decode("utf-8")
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: linear-gradient(rgba(0,0,0,0.72), rgba(0,0,0,0.72)), url("data:{mime};base64,{encoded}");
                background-size: cover;
                background-attachment: fixed;
                background-position: center;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )


def sidebar_header():
    with st.sidebar:
        st.markdown(f"<div class='ssc-app-name'>{APP_TITLE}</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='ssc-app-description'>Internal Event Management System</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr class='ssc-sidebar-divider'>", unsafe_allow_html=True)


def sidebar_navigation(role="volunteer"):
    with st.sidebar:
        st.markdown("<div class='ssc-sidebar-group'>Overview</div>", unsafe_allow_html=True)
        st.page_link("pages/home.py", label="Home", icon="🏠")

        st.markdown("<div class='ssc-sidebar-group'>Event Management</div>", unsafe_allow_html=True)
        if role == "admin":
            st.page_link("pages/create_event.py", label="Create Event", icon="➕")
        st.page_link("pages/event_workspace.py", label="Event Workspace", icon="🎟️")
        if role == "admin":
            st.page_link("pages/event_analytics.py", label="Event Analytics", icon="📊")

            st.markdown("<div class='ssc-sidebar-group'>Data Management</div>", unsafe_allow_html=True)
            st.page_link("pages/database.py", label="Database", icon="🗄️")
            st.page_link("pages/audit_log.py", label="Audit Log", icon="🧾")


def sidebar_footer():
    from auth import logout

    logo = _first_existing(["ssc_logo.png", "ssc_logo.jpg", "logo.png", "logo.jpg"])
    with st.sidebar:
        st.divider()
        st.markdown(f"<div class='ssc-club-footer'>{SIDEBAR_TITLE}®</div>", unsafe_allow_html=True)
        if logo:
            st.image(str(logo), use_container_width=True)
        display_name = st.session_state.get("display_name", st.session_state.get("username", ""))
        role = st.session_state.get("role", "volunteer").title()
        st.markdown(f"**Signed in as:** {html.escape(str(display_name))}")
        st.caption(f"Role: {role}")
        if st.button("Log out", use_container_width=True):
            logout()


def page_header(title, page_name=None, description=None):
    st.markdown(
        f"<h1 class='ssc-page-title'>{html.escape(str(title))}</h1>",
        unsafe_allow_html=True,
    )
    if page_name or description:
        st.markdown(
            f"""
            <div class="ssc-page-meta">
                <span class="ssc-page-pill">{html.escape(str(page_name or ""))}</span>
                <span class="ssc-page-description">{html.escape(str(description or ""))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.divider()


def colored_heading(text, color=PRIMARY):
    st.markdown(
        f"<h3 style='color:{color}; margin-top: .9rem; margin-bottom: .45rem;'>{html.escape(str(text))}</h3>",
        unsafe_allow_html=True,
    )


def basic_info(label, value):
    st.markdown(
        f"""
        <div class="ssc-basic-info">
            <div class="ssc-basic-info-label">{html.escape(str(label))}</div>
            <div class="ssc-basic-info-value">{html.escape(str(value or '-'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _image_html(path):
    if path is None:
        return "<div class='ssc-event-image'>🎟️</div>"
    if isinstance(path, float) and math.isnan(path):
        return "<div class='ssc-event-image'>🎟️</div>"
    if not isinstance(path, (str, Path)):
        return "<div class='ssc-event-image'>🎟️</div>"
    path = str(path).strip()
    if not path or path.lower() == "nan":
        return "<div class='ssc-event-image'>🎟️</div>"
    image_path = Path(path)
    if not image_path.is_absolute():
        image_path = Path(__file__).parent / image_path
    if not image_path.exists():
        return "<div class='ssc-event-image'>🎟️</div>"
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"<div class='ssc-event-image'><img src='data:{mime};base64,{encoded}' alt='Event image'></div>"


def event_card(row, past=False):
    registered = int(row.get("registration_count") or 0)
    attended = int(row.get("attended_count") or 0)
    rate = f"{attended / registered:.0%}" if registered else "-"
    time_text = row.get("start_datetime") or "-"
    location = row.get("location_name") or "-"
    event_type = row.get("etype_name") or "-"
    stats = ""
    if past:
        stats = (
            f"<hr class='ssc-event-divider'>"
            f"<div style='font-size:.92rem;'>"
            f"<strong>{registered}</strong> registered · "
            f"<strong>{attended}</strong> attended · "
            f"<strong>{rate}</strong> rate"
            f"</div>"
        )
    image = _image_html(row.get("event_image_path"))
    st.markdown(
        f"""
        <div class="ssc-event-card">
            {image}
            <h4 class="ssc-event-title">{html.escape(str(row.get('event_name') or '-'))}</h4>
            <hr class='ssc-event-divider'>
            <div class="ssc-event-info-grid">
                <div>📍 {html.escape(str(location))} - {html.escape(str(event_type))}</div>
                <div>🕒 {html.escape(str(time_text))}</div>
            </div>
            {stats}
        </div>
        """,
        unsafe_allow_html=True,
    )
