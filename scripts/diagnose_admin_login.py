"""Safely diagnose CineScope Admin login settings from a local terminal."""

import getpass
import hmac
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import dotenv_values, load_dotenv

from frontend.auth import (
    ADMIN_PASSWORD_HASH_ENV,
    ADMIN_USERNAME_ENV,
    PROJECT_ENV_PATH,
    password_hash_format_is_valid,
    verify_password,
)


def main():
    file_values = dotenv_values(PROJECT_ENV_PATH)
    file_username = file_values.get(ADMIN_USERNAME_ENV) or ""
    file_hash = file_values.get(ADMIN_PASSWORD_HASH_ENV) or ""

    # Match the app's default precedence: process environment variables win.
    load_dotenv(dotenv_path=PROJECT_ENV_PATH)
    configured_username = os.getenv(ADMIN_USERNAME_ENV, "").strip()
    stored_hash = os.getenv(ADMIN_PASSWORD_HASH_ENV, "").strip()

    print("CineScope Admin login diagnostics (no credentials will be displayed).")
    entered_username = input("Admin username to check: ").strip()
    entered_password = getpass.getpass("Admin password to check (input hidden): ")

    username_matches = bool(configured_username) and hmac.compare_digest(
        entered_username, configured_username
    )
    hash_is_valid = password_hash_format_is_valid(stored_hash)
    password_verifies = hash_is_valid and verify_password(entered_password, stored_hash)
    environment_matches_file = (
        configured_username == file_username.strip()
        and stored_hash == file_hash.strip()
    )

    print(f"Admin values are configured: {bool(configured_username and stored_hash)}")
    print(f"Application environment matches .env: {environment_matches_file}")
    print(f"Username matches configured value: {username_matches}")
    print(f"Stored password hash format is valid: {hash_is_valid}")
    print(f"Password verification succeeds: {password_verifies}")
    del entered_password, stored_hash, file_hash
    return 0 if username_matches and password_verifies else 1


if __name__ == "__main__":
    raise SystemExit(main())
