"""CineScope entry point with shared top navigation."""

from pathlib import Path

import streamlit as st

from frontend.auth import (
    current_role,
    initialize_auth_state,
    is_admin,
    logout,
    navigation_items,
)
from frontend.analytics import render_analytics
from frontend.home import render_home
from frontend.login import render_login
from frontend.manage import render_manage
from frontend.ml_page import render_ml_page
from frontend.movies import render_movies


st.set_page_config(page_title="CineScope", page_icon="C", layout="wide")


def load_stylesheet():
    """Load the shared styles from frontend/style.css."""
    css_path = Path(__file__).parent / "frontend" / "style.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def select_page(page_name):
    """Remember the selected page after a navigation button is clicked."""
    if page_name == "Manage" and not is_admin():
        st.session_state["cinescope_page"] = "Home"
        st.session_state["manage_access_denied"] = True
        return
    st.session_state["cinescope_page"] = page_name


def select_auth_action():
    """Show Login to viewers and log out Admins."""
    if is_admin():
        logout()
        st.session_state["cinescope_page"] = "Home"
    else:
        st.session_state["cinescope_page"] = "Login"


load_stylesheet()
initialize_auth_state()

if "cinescope_page" not in st.session_state:
    st.session_state["cinescope_page"] = "Home"

page_labels = navigation_items()
page_functions = {
    "Home": render_home,
    "Movies": render_movies,
    "Analytics": render_analytics,
    "ML Studio": render_ml_page,
    "Manage": render_manage,
    "Login": render_login,
}

if st.session_state["cinescope_page"] == "Manage" and not is_admin():
    st.session_state["cinescope_page"] = "Home"
    st.session_state["manage_access_denied"] = True
if st.session_state["cinescope_page"] not in page_functions:
    st.session_state["cinescope_page"] = "Home"

brand_column, *nav_columns = st.columns([1.7] + [1] * len(page_labels))
with brand_column:
    st.markdown(
        '<div class="top-nav-brand"><span class="brand-mark">C</span><span>CineScope</span>'
        f'<span class="role-badge">{current_role()}</span></div>',
        unsafe_allow_html=True,
    )

for column, label in zip(nav_columns, page_labels):
    with column:
        active = st.session_state["cinescope_page"] == label
        st.button(
            label,
            key=f"nav_{label.lower().replace(' ', '_')}",
            type="primary" if active and label != "Logout" else "secondary",
            use_container_width=True,
            on_click=select_auth_action if label in ("Login", "Logout") else select_page,
            args=() if label in ("Login", "Logout") else (label,),
        )
        if active:
            st.markdown('<div class="nav-active-indicator"></div>', unsafe_allow_html=True)

st.markdown('<div class="top-nav-divider"></div>', unsafe_allow_html=True)

if st.session_state.pop("manage_access_denied", False):
    st.error("Admin access is required to manage movies.")
page_functions[st.session_state["cinescope_page"]]()
