"""Session roles and environment-backed admin authentication."""

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=PROJECT_ENV_PATH)

ADMIN_USERNAME_ENV = "CINESCOPE_ADMIN_USERNAME"
ADMIN_PASSWORD_HASH_ENV = "CINESCOPE_ADMIN_PASSWORD_HASH"
PBKDF2_ITERATIONS = 600_000


def hash_password(password):
    """Create a salted PBKDF2 hash suitable for storage in .env."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${encode(salt)}${encode(digest)}"


def verify_password(password, stored_hash):
    """Compare a password against the salted hash stored in the environment."""
    try:
        algorithm, rounds, salt_text, digest_text = stored_hash.split("$", 3)
        rounds = int(rounds)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= rounds <= 2_000_000:
            return False

        def decode(value):
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        salt = decode(salt_text)
        expected = decode(digest_text)
        if len(salt) != 16 or len(expected) != hashlib.sha256().digest_size:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError):
        return False


def password_hash_format_is_valid(stored_hash):
    """Check the salted PBKDF2 format without revealing any hash content."""
    try:
        algorithm, rounds, salt_text, digest_text = stored_hash.split("$", 3)
        rounds = int(rounds)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= rounds <= 2_000_000:
            return False

        def decode(value):
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        salt = decode(salt_text)
        digest = decode(digest_text)
        return len(salt) == 16 and len(digest) == hashlib.sha256().digest_size
    except (AttributeError, TypeError, ValueError):
        return False


def admin_login_is_configured():
    return bool(
        os.getenv(ADMIN_USERNAME_ENV, "").strip()
        and os.getenv(ADMIN_PASSWORD_HASH_ENV, "").strip()
    )


def authenticate_admin(username, password):
    """Validate credentials without logging or returning secret values."""
    configured_username = os.getenv(ADMIN_USERNAME_ENV, "").strip()
    stored_hash = os.getenv(ADMIN_PASSWORD_HASH_ENV, "").strip()
    if (
        not configured_username
        or not stored_hash
        or not isinstance(username, str)
        or not isinstance(password, str)
        or not username
        or not password
    ):
        return False
    return hmac.compare_digest(username.strip(), configured_username) and verify_password(
        password, stored_hash
    )


def login_admin(username, password):
    """Set the Admin role only after credential verification succeeds."""
    if not authenticate_admin(username, password):
        return False
    st.session_state["cinescope_role"] = "admin"
    st.session_state["cinescope_username"] = username.strip()
    return True


def initialize_auth_state():
    """Give signed-out sessions the read-only Viewer role."""
    role = st.session_state.get("cinescope_role")
    if role not in ("viewer", "admin"):
        role = "viewer"
        st.session_state["cinescope_role"] = role
    if role == "admin" and not is_admin():
        logout()


def current_role():
    return "Admin" if is_admin() else "Viewer"


def navigation_items():
    """Return the pages allowed for this session, with its login/logout action."""
    items = ["Home", "Movies", "Analytics", "ML Studio"]
    if is_admin():
        items.append("Manage")
    items.append("Logout" if is_admin() else "Login")
    return items


def is_admin():
    username = st.session_state.get("cinescope_username", "")
    configured_username = os.getenv(ADMIN_USERNAME_ENV, "").strip()
    return (
        st.session_state.get("cinescope_role") == "admin"
        and isinstance(username, str)
        and bool(username)
        and bool(configured_username)
        and hmac.compare_digest(username, configured_username)
    )


def require_admin():
    """Raise before any CRUD operation unless this session is an Admin."""
    if not is_admin():
        raise PermissionError("Admin access is required for movie changes.")


def logout():
    st.session_state.pop("cinescope_username", None)
    st.session_state["cinescope_role"] = "viewer"
