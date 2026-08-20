"""Simple session-based authentication for the SSC Streamlit app."""

from __future__ import annotations

import hmac
import time

import streamlit as st


MAX_LOGIN_ATTEMPTS = 5
LOCK_SECONDS = 30


def _users_from_secrets():
    """Return configured users without exposing passwords to the UI."""
    try:
        auth_config = st.secrets.get("auth", {})
        users = auth_config.get("users", {})
    except Exception:
        return {}
    return {str(username).strip().lower(): details for username, details in users.items()}


def _show_missing_config():
    st.error("Login is not configured yet.")
    st.info(
        "Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` "
        "for local use, or add the same values to Streamlit Cloud → App settings → Secrets."
    )


def require_login():
    """Render the login screen until a configured account is authenticated."""
    if st.session_state.get("authenticated") is True:
        return True

    st.markdown(
        """
        <div style="max-width:460px; margin:7vh auto 1.25rem auto; text-align:center;">
            <div style="font-size:2.35rem;">🎟️</div>
            <h1 style="color:#c61770; margin:.35rem 0;">Special Social Event Hub</h1>
            <p style="opacity:.72;">Sign in to continue</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    users = _users_from_secrets()
    if not users:
        _show_missing_config()
        return False

    locked_until = float(st.session_state.get("login_locked_until", 0))
    remaining = max(0, int(locked_until - time.time()))
    if remaining:
        st.warning(f"Too many unsuccessful attempts. Try again in {remaining + 1} seconds.")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="admin-1")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button(
            "Log in",
            type="primary",
            use_container_width=True,
            disabled=bool(remaining),
        )

    if not submitted or remaining:
        return False

    normalized_username = username.strip().lower()
    account = users.get(normalized_username)
    configured_password = str(account.get("password", "")) if account else ""
    password_matches = bool(configured_password) and hmac.compare_digest(
        password.encode("utf-8"), configured_password.encode("utf-8")
    )

    if not account or not password_matches:
        attempts = int(st.session_state.get("failed_login_attempts", 0)) + 1
        st.session_state.failed_login_attempts = attempts
        if attempts >= MAX_LOGIN_ATTEMPTS:
            st.session_state.login_locked_until = time.time() + LOCK_SECONDS
            st.session_state.failed_login_attempts = 0
        st.error("Incorrect username or password.")
        return False

    role = str(account.get("role", "volunteer")).strip().lower()
    if role not in {"admin", "volunteer"}:
        st.error(f"Account '{normalized_username}' has an unsupported role.")
        return False

    st.session_state.authenticated = True
    st.session_state.username = normalized_username
    st.session_state.display_name = str(account.get("display_name", normalized_username))
    st.session_state.role = role
    st.session_state.operator_name = normalized_username
    st.session_state.failed_login_attempts = 0
    st.session_state.login_locked_until = 0
    st.rerun()
    return True


def logout():
    """Clear authentication and operator state for the current browser session."""
    for key in (
        "authenticated",
        "username",
        "display_name",
        "role",
        "operator_name",
        "failed_login_attempts",
        "login_locked_until",
    ):
        st.session_state.pop(key, None)
    st.rerun()
