"""Provision the production smoke-child account idempotently.

The 2026-04-13 adult smoke account (smoke@scout.app) was created via
an ad-hoc /tmp/full_smoke_verify.py script that never made it into
the repo. That was the antipattern this script refuses to repeat:
every write path is in version control, idempotent, and auditable
from the commit trail.

What this script creates or updates (all in the Roberts family on
prod Railway):

  - scout.family_members row first_name='Smoke-Child' last_name='Roberts'
    role='child' if missing
  - scout.user_accounts row email='smoke-child@scout.app' linked to
    the above family_member if missing
  - scout.role_tier_overrides row pointing the family_member at the
    CHILD tier (UPPERCASE, post-migration 034) if missing
  - Sets user_accounts.password_hash to a fresh bcrypt hash generated
    from a new 43-char URL-safe token, every run
  - Verifies the new password authenticates via a live login round-
    trip against https://scout-backend-production-9991.up.railway.app
  - Prints the token ONCE at the end so the operator can set the
    matching Railway env var SCOUT_SMOKE_CHILD_PASSWORD and GitHub
    secret of the same name

Usage:

  SCOUT_DATABASE_URL=postgresql://... python scripts/provision_smoke_child.py

The SCOUT_DATABASE_URL must point at the public Railway proxy URL
(not the internal one). Andrew's live value is in 1Password under
the Railway Postgres entry.

Safety:

  - All DB writes are wrapped in a single transaction; commit only
    if every step succeeds.
  - Every INSERT path is guarded by a SELECT first. Refuses to run
    if any pre-count assertion fails (e.g. the Roberts family is
    missing, or more than one match exists on a supposedly-unique
    WHERE).
  - Does NOT touch the adult smoke account, any other family member,
    any other user account, or any row outside the Roberts family.
"""

from __future__ import annotations

import os
import secrets
import sys
from datetime import date

import requests
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.services.auth_service import hash_password  # noqa: E402


ROBERTS_FAMILY_NAME = "Roberts"
CHILD_EMAIL = "smoke-child@scout.app"
CHILD_FIRST_NAME = "Smoke-Child"
CHILD_LAST_NAME = "Roberts"
CHILD_ROLE = "child"
CHILD_TIER_NAME = "CHILD"
# A benign birthdate that clearly signals "bot" if anyone reads the
# UI. Keep stable so re-runs do not cause noise.
CHILD_BIRTHDATE = date(2015, 1, 1)
LOGIN_URL = "https://scout-backend-production-9991.up.railway.app/api/auth/login"


def _require_env() -> str:
    url = os.environ.get("SCOUT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        sys.exit(
            "ERROR: set SCOUT_DATABASE_URL to the Railway public proxy "
            "URL before running this script."
        )
    return url


def _upsert_family_member(conn, family_id) -> tuple:
    """Return (family_member_id, created_now: bool)."""
    existing = conn.execute(
        text(
            """
            SELECT id FROM family_members
            WHERE family_id = :fid
              AND first_name = :fn
              AND last_name = :ln
            """
        ),
        {"fid": family_id, "fn": CHILD_FIRST_NAME, "ln": CHILD_LAST_NAME},
    ).fetchall()
    if len(existing) > 1:
        sys.exit(
            f"ERROR: {len(existing)} family_member rows match "
            f"{CHILD_FIRST_NAME} {CHILD_LAST_NAME} in Roberts; refusing "
            f"to update any of them."
        )
    if existing:
        return existing[0].id, False
    inserted = conn.execute(
        text(
            """
            INSERT INTO family_members
              (family_id, first_name, last_name, role, birthdate, is_active)
            VALUES
              (:fid, :fn, :ln, :role, :bd, true)
            RETURNING id
            """
        ),
        {
            "fid": family_id,
            "fn": CHILD_FIRST_NAME,
            "ln": CHILD_LAST_NAME,
            "role": CHILD_ROLE,
            "bd": CHILD_BIRTHDATE,
        },
    ).fetchone()
    return inserted.id, True


def _upsert_tier_override(conn, family_member_id) -> bool:
    """Return True if override was created, False if already present.

    Assigns CHILD tier. Never downgrades an existing tier assignment
    (e.g. if the member already points at TEEN because an operator
    changed it manually, we leave it alone).
    """
    tier_row = conn.execute(
        text("SELECT id FROM role_tiers WHERE name = :n"),
        {"n": CHILD_TIER_NAME},
    ).fetchone()
    if tier_row is None:
        sys.exit(
            f"ERROR: role_tiers row for '{CHILD_TIER_NAME}' not found. "
            f"Did migration 034 run?"
        )
    existing = conn.execute(
        text(
            "SELECT id, role_tier_id FROM role_tier_overrides "
            "WHERE family_member_id = :fm"
        ),
        {"fm": family_member_id},
    ).fetchone()
    if existing is not None:
        return False
    conn.execute(
        text(
            """
            INSERT INTO role_tier_overrides
              (family_member_id, role_tier_id, override_permissions, override_behavior)
            VALUES
              (:fm, :tier, '{}'::jsonb, '{}'::jsonb)
            """
        ),
        {"fm": family_member_id, "tier": tier_row.id},
    )
    return True


def _upsert_user_account(conn, family_member_id, password_hash_value) -> tuple:
    """Return (user_account_id, created_now: bool)."""
    existing = conn.execute(
        text("SELECT id FROM user_accounts WHERE email = :em"),
        {"em": CHILD_EMAIL},
    ).fetchall()
    if len(existing) > 1:
        sys.exit(
            f"ERROR: {len(existing)} user_accounts rows match "
            f"{CHILD_EMAIL}; refusing to update any of them."
        )
    if existing:
        conn.execute(
            text(
                "UPDATE user_accounts SET password_hash = :h, "
                "is_active = true WHERE email = :em"
            ),
            {"h": password_hash_value, "em": CHILD_EMAIL},
        )
        return existing[0].id, False
    inserted = conn.execute(
        text(
            """
            INSERT INTO user_accounts
              (family_member_id, email, auth_provider, password_hash,
               is_primary, is_active)
            VALUES
              (:fm, :em, 'email', :h, false, true)
            RETURNING id
            """
        ),
        {"fm": family_member_id, "em": CHILD_EMAIL, "h": password_hash_value},
    ).fetchone()
    return inserted.id, True


def _verify_login(password: str) -> bool:
    """Hit the prod login endpoint; return True if token comes back."""
    try:
        r = requests.post(
            LOGIN_URL,
            json={"email": CHILD_EMAIL, "password": password},
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"WARN: login verification request failed: {exc}")
        return False
    if r.status_code != 200:
        print(f"WARN: login returned {r.status_code}: {r.text[:200]}")
        return False
    body = r.json()
    return bool(
        body.get("token") or body.get("access_token") or body.get("session_token")
    )


def main() -> int:
    db_url = _require_env()
    engine = create_engine(db_url)

    token = secrets.token_urlsafe(32)  # 43 chars URL-safe
    assert len(token) == 43, f"expected 43-char token; got {len(token)}"
    hashed = hash_password(token)

    with engine.begin() as conn:
        fam = conn.execute(
            text("SELECT id FROM families WHERE name = :n"),
            {"n": ROBERTS_FAMILY_NAME},
        ).fetchone()
        if fam is None:
            sys.exit(
                f"ERROR: no family named '{ROBERTS_FAMILY_NAME}' on this "
                f"database. Refusing to create one; this script only "
                f"provisions the child account in an existing family."
            )
        family_id = fam.id

        fm_id, fm_created = _upsert_family_member(conn, family_id)
        tier_created = _upsert_tier_override(conn, fm_id)
        ua_id, ua_created = _upsert_user_account(conn, fm_id, hashed)

    print()
    print("DB writes complete:")
    print(f"  family_member  : {fm_id}  (created={fm_created})")
    print(f"  user_account   : {ua_id}  (created={ua_created})")
    print(f"  tier override  : CHILD     (created={tier_created})")
    print()

    if _verify_login(token):
        print("LOGIN VERIFIED: POST /api/auth/login returned 200 with token.")
    else:
        print("LOGIN FAILED after DB write. Check Railway backend health.")
        return 1

    print()
    print("=" * 60)
    print("Set these values once the script finishes:")
    print()
    print(f"  Railway env (scout-backend):")
    print(f"    SCOUT_SMOKE_CHILD_EMAIL     = {CHILD_EMAIL}")
    print(f"    SCOUT_SMOKE_CHILD_PASSWORD  = {token}")
    print()
    print(f"  GitHub repo secrets:")
    print(f"    SCOUT_SMOKE_CHILD_EMAIL     = {CHILD_EMAIL}")
    print(f"    SCOUT_SMOKE_CHILD_PASSWORD  = {token}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
