"""Login page for the CineScope Admin role."""

import streamlit as st

from frontend.auth import admin_login_is_configured, is_admin, login_admin, logout


def _submit_admin_login():
    username = st.session_state.get("cinescope_admin_username_input", "")
    password = st.session_state.get("cinescope_admin_password_input", "")
    if login_admin(username, password):
        st.session_state["cinescope_login_error"] = False
    else:
        st.session_state["cinescope_login_error"] = True
    st.session_state["cinescope_admin_password_input"] = ""


def render_login():
    if is_admin():
        st.markdown(
            "<p class='eyebrow page-eyebrow'>ACCOUNT</p><h1>Administrator access</h1>",
            unsafe_allow_html=True,
        )
        st.success("You are signed in with the Admin role.")
        if st.button("Log out", key="account_logout", type="secondary"):
            logout()
            st.session_state["cinescope_page"] = "Home"
            st.rerun()
        return

    st.markdown(
        "<p class='eyebrow page-eyebrow'>CINESCOPE ACCOUNT</p><h1>Admin login</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Viewer access is available without signing in. Admin access is required to manage movies.")

    if not admin_login_is_configured():
        st.warning(
            "Admin login is not configured. Set CINESCOPE_ADMIN_USERNAME and "
            "CINESCOPE_ADMIN_PASSWORD_HASH in the ignored .env file."
        )

    with st.form("admin_login_form"):
        st.text_input(
            "Username",
            key="cinescope_admin_username_input",
            autocomplete="username",
        )
        st.text_input(
            "Password",
            key="cinescope_admin_password_input",
            type="password",
            autocomplete="current-password",
        )
        st.form_submit_button(
            "Log in",
            type="primary",
            on_click=_submit_admin_login,
        )

    if st.session_state.pop("cinescope_login_error", False):
        st.error("The username or password is incorrect.")
