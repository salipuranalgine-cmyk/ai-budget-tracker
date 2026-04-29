from __future__ import annotations

import os
from pathlib import Path
import sys

import msvcrt


def _bootstrap_venv_site_packages() -> None:
    project_root = Path(__file__).resolve().parent
    site_packages = project_root / "venv" / "Lib" / "site-packages"
    if site_packages.exists():
        sys.path.insert(0, str(site_packages))


_bootstrap_venv_site_packages()

from backend import database as db
import user_manager as um


def _read_masked_input(prompt: str) -> str:
    print(prompt, end="", flush=True)
    chars: list[str] = []
    while True:
        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            print()
            return "".join(chars)
        if key == "\003":
            raise KeyboardInterrupt
        if key == "\b":
            if chars:
                chars.pop()
                print("\b \b", end="", flush=True)
            continue
        if key in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue
        chars.append(key)
        print("*", end="", flush=True)


def main() -> int:
    backend = db.get_backend()
    if backend != "postgres":
        print("DATABASE_URL is not set to PostgreSQL in this terminal.")
        print("Set DATABASE_URL first, then run this script again.")
        return 1

    if len(sys.argv) > 1:
        new_password = sys.argv[1].strip()
        confirm_password = new_password
    else:
        new_password = _read_masked_input("Enter new master admin password: ").strip()
        confirm_password = _read_masked_input("Confirm new master admin password: ").strip()

    if not new_password:
        print("Password was empty. Nothing changed.")
        return 1

    if new_password != confirm_password:
        print("Passwords did not match. Nothing changed.")
        return 1

    um.init_users_db()
    um.set_master_admin_password(new_password)
    dsn = os.getenv("DATABASE_URL", "")
    safe_dsn = dsn.rsplit("@", 1)[-1] if "@" in dsn else dsn
    print(f"Master admin password updated in PostgreSQL app_state ({safe_dsn}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
