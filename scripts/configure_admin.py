"""Set up CineScope's first Admin credentials from a local terminal."""

import getpass
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
USERNAME_KEY = "CINESCOPE_ADMIN_USERNAME"
PASSWORD_HASH_KEY = "CINESCOPE_ADMIN_PASSWORD_HASH"

# Make the existing application authentication helpers importable when this
# script is launched directly from the scripts directory.
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from frontend.auth import authenticate_admin, hash_password, admin_login_is_configured


def _write_admin_values(username, password_hash):
    """Replace only the two Admin settings, preserving every other .env line."""
    if ENV_PATH.exists():
        original = ENV_PATH.read_bytes().decode("utf-8")
    else:
        original = ""

    newline = "\r\n" if "\r\n" in original else "\n"
    replacements = {
        USERNAME_KEY: f'{USERNAME_KEY}="{username}"',
        PASSWORD_HASH_KEY: f'{PASSWORD_HASH_KEY}="{password_hash}"',
    }
    found = set()
    updated_lines = []

    for line in original.splitlines(keepends=True):
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and match.group(1) in replacements:
            key = match.group(1)
            updated_lines.append(replacements[key] + newline)
            found.add(key)
        else:
            updated_lines.append(line)

    if updated_lines and not updated_lines[-1].endswith(("\n", "\r")):
        updated_lines[-1] += newline
    for key, value in replacements.items():
        if key not in found:
            updated_lines.append(value + newline)

    # Write directly to the ignored .env file; no temporary copy of its secrets
    # is created. Other environment variables and comments remain untouched.
    ENV_PATH.write_bytes("".join(updated_lines).encode("utf-8"))


def main():
    print("CineScope Admin setup (credentials stay in this local terminal).")
    username = input("Admin username: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", username):
        print("Use 1–64 letters, numbers, dots, underscores, @ signs, or hyphens.")
        return 1

    password = getpass.getpass("Admin password (input hidden): ")
    confirmation = getpass.getpass("Confirm password (input hidden): ")
    if not password or password != confirmation:
        print("Passwords were empty or did not match. No changes were made.")
        return 1

    password_hash = hash_password(password)
    _write_admin_values(username, password_hash)

    # Reload from this exact file and verify using the app's own login routine.
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    configured = admin_login_is_configured()
    credentials_work = authenticate_admin(username, password)
    del password, confirmation, password_hash

    if not (configured and credentials_work):
        print("Admin settings were written, but local authentication verification failed.")
        return 1

    print("Admin configuration saved and verified. No credential values were displayed.")
    print("Restart the Streamlit app so its process loads the updated .env values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
