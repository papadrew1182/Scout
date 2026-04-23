"""Pre-sprint quiesce verification for the canonical rewrite sprint.

Companion doc: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
               Section 6 (Quiesce plan) and Phase 0 PR 0.2.

This script is verify-only for Railway env vars. Andrew sets the env vars
manually via the Railway dashboard; the script confirms the flips landed
and then runs the one active operation (Supabase Storage bucket purge).

Usage:

    SCOUT_DATABASE_URL=postgresql://... \\
    SCOUT_API_URL=https://scout-backend-production-9991.up.railway.app \\
    SCOUT_SUPABASE_URL=https://xxx.supabase.co \\
    SCOUT_SUPABASE_SERVICE_ROLE_KEY=eyJ... \\
        python scripts/quiesce_prod.py

Env var defaults:
    SCOUT_API_URL defaults to the production Railway URL.
    SCOUT_SUPABASE_STORAGE_BUCKET defaults to "attachments".

Idempotent. Running a second time re-confirms state and re-purges an
already-empty bucket (no error).

Flow:

    1. Smoke-test the API URL and DB URL.
    2. Print current /ready snapshot so the operator sees current state.
    3. Prompt: flip three Railway env vars, press Enter when done.
    4. Verify via /ready: bootstrap_enabled=true, ai_available=false.
    5. Prompt: confirm SCOUT_SCHEDULER_ENABLED=false is set, press Enter.
    6. Poll public.scout_scheduled_runs for 5 minutes.
       Pass conditions: no new rows created after baseline AND no in-flight
       rows (run_started_at IS NOT NULL AND run_ended_at IS NULL).
    7. Purge Supabase Storage attachments bucket (list + delete all objects).
    8. Print summary. Exit 0 on success, non-zero on any failure.

Non-goals:
    - Does NOT set Railway env vars. Operator does that via dashboard.
    - Does NOT truncate or drop any table. That is Phase 1.
    - Does NOT touch Supabase Auth. None is integrated.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import create_engine, text

DEFAULT_API_URL = "https://scout-backend-production-9991.up.railway.app"
DEFAULT_BUCKET = "attachments"

# Scheduler tick interval is 5 minutes. A full idle window means
# polling for at least one full interval with no activity.
SCHEDULER_POLL_SECONDS = 5 * 60
SCHEDULER_POLL_STEP_SECONDS = 30

# Supabase list returns up to `limit` objects per call; page through.
SUPABASE_LIST_PAGE_SIZE = 1000


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"[quiesce] {msg}")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Environment variable {name} is required but not set.")
    return value


def read_ready(api_url: str) -> dict:
    """GET /ready and return the JSON. Raises on non-200 or non-JSON."""
    url = f"{api_url.rstrip('/')}/ready"
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException as e:
        fail(f"GET {url} failed: {e}")
    if resp.status_code != 200:
        fail(f"GET {url} returned HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError:
        fail(f"GET {url} returned non-JSON: {resp.text[:200]}")
    return {}  # unreachable, satisfies type checker


def prompt_enter(message: str) -> None:
    """Print a message and wait for Enter. Flushes stdout so the prompt appears."""
    sys.stdout.write(message)
    sys.stdout.flush()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        fail("Aborted by operator.")


def verify_bootstrap_and_ai(api_url: str) -> None:
    info("Verifying SCOUT_ENABLE_BOOTSTRAP=true and SCOUT_ENABLE_AI=false via /ready...")
    ready = read_ready(api_url)
    bootstrap_enabled = ready.get("bootstrap_enabled")
    ai_available = ready.get("ai_available")
    info(f"  /ready: bootstrap_enabled={bootstrap_enabled}, ai_available={ai_available}")
    if bootstrap_enabled is not True:
        fail(
            "Expected bootstrap_enabled=true in /ready after env flip. "
            "Confirm SCOUT_ENABLE_BOOTSTRAP=true is set on Railway and the service has redeployed."
        )
    # ai_available = enable_ai AND bool(anthropic_api_key). Either False-cause is acceptable:
    # the belt-and-suspenders goal is only "AI writes gated off".
    if ai_available is not False:
        fail(
            "Expected ai_available=false in /ready after env flip. "
            "Confirm SCOUT_ENABLE_AI=false is set on Railway and the service has redeployed."
        )
    info("  verified: bootstrap enabled, AI unavailable")


def poll_scheduler_idle(db_url: str) -> None:
    """Poll public.scout_scheduled_runs for 5 minutes; verify no activity."""
    info(
        f"Polling public.scout_scheduled_runs for {SCHEDULER_POLL_SECONDS // 60} minutes to confirm scheduler idle..."
    )
    baseline_ts = datetime.now(timezone.utc)
    engine = create_engine(db_url, future=True)

    deadline = time.monotonic() + SCHEDULER_POLL_SECONDS
    step = 0
    while time.monotonic() < deadline:
        step += 1
        with engine.connect() as conn:
            # New rows created after the baseline.
            new_rows = conn.execute(
                text(
                    "SELECT count(*) FROM public.scout_scheduled_runs "
                    "WHERE created_at > :baseline"
                ),
                {"baseline": baseline_ts},
            ).scalar_one()
            # In-flight rows (started but not ended). Defensive: any history row
            # with a non-null run_started_at but null run_ended_at counts.
            in_flight = conn.execute(
                text(
                    "SELECT count(*) FROM public.scout_scheduled_runs "
                    "WHERE run_started_at IS NOT NULL AND run_ended_at IS NULL"
                )
            ).scalar_one()
        elapsed = int(time.monotonic() - (deadline - SCHEDULER_POLL_SECONDS))
        info(f"  step {step}: elapsed={elapsed}s, new_rows={new_rows}, in_flight={in_flight}")
        if new_rows > 0:
            fail(
                f"Scheduler is NOT idle: {new_rows} row(s) created after baseline "
                f"{baseline_ts.isoformat()}. Scheduler is still ticking."
            )
        if in_flight > 0:
            fail(
                f"Scheduler has {in_flight} in-flight run(s) (run_started_at set, run_ended_at null). "
                "Wait for the current tick to complete or investigate stuck jobs."
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(SCHEDULER_POLL_STEP_SECONDS, max(remaining, 1)))
    info("  verified: scheduler is idle for the full window")


def list_supabase_objects(supabase_url: str, service_role_key: str, bucket: str) -> list[str]:
    """Return all object paths in the bucket. Paginates."""
    paths: list[str] = []
    offset = 0
    while True:
        url = f"{supabase_url.rstrip('/')}/storage/v1/object/list/{bucket}"
        body = {"limit": SUPABASE_LIST_PAGE_SIZE, "offset": offset, "prefix": ""}
        headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
        except requests.RequestException as e:
            fail(f"Supabase list failed: {e}")
        if resp.status_code != 200:
            fail(f"Supabase list returned HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            batch = resp.json()
        except ValueError:
            fail(f"Supabase list returned non-JSON: {resp.text[:300]}")
        if not isinstance(batch, list):
            fail(f"Supabase list returned unexpected shape: {type(batch).__name__}")
        if not batch:
            break
        for obj in batch:
            name = obj.get("name") if isinstance(obj, dict) else None
            if not name:
                # Skip folder placeholders (name is null for pseudo-directories).
                continue
            # The list API is non-recursive at prefix="". If the deployment uses
            # subdirectories, a recursive purge needs an enumerate-then-recurse.
            # The current deployment's upload path is a single flat bucket
            # (see backend/app/services/storage.py delete_file pattern), so flat
            # enumeration suffices. If this assumption changes, extend.
            paths.append(name)
        if len(batch) < SUPABASE_LIST_PAGE_SIZE:
            break
        offset += SUPABASE_LIST_PAGE_SIZE
    return paths


def delete_supabase_objects(
    supabase_url: str, service_role_key: str, bucket: str, paths: list[str]
) -> None:
    """Bulk-delete all named paths from the bucket."""
    if not paths:
        return
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": "application/json",
    }
    # Delete in chunks. Supabase accepts arbitrary list lengths but chunking
    # keeps request bodies reasonable.
    chunk = 200
    for i in range(0, len(paths), chunk):
        body = {"prefixes": paths[i : i + chunk]}
        try:
            resp = requests.delete(url, json=body, headers=headers, timeout=60)
        except requests.RequestException as e:
            fail(f"Supabase delete failed (chunk {i}): {e}")
        if resp.status_code not in (200, 204):
            fail(
                f"Supabase delete returned HTTP {resp.status_code} (chunk {i}): "
                f"{resp.text[:300]}"
            )


def purge_supabase_bucket(supabase_url: str, service_role_key: str, bucket: str) -> None:
    info(f"Purging Supabase Storage bucket '{bucket}' at {supabase_url} ...")
    paths = list_supabase_objects(supabase_url, service_role_key, bucket)
    info(f"  found {len(paths)} object(s) to delete")
    delete_supabase_objects(supabase_url, service_role_key, bucket, paths)
    # Re-list to confirm empty (idempotence check).
    remaining = list_supabase_objects(supabase_url, service_role_key, bucket)
    if remaining:
        fail(
            f"After delete, bucket still has {len(remaining)} object(s). "
            "Check Supabase Storage policies or rerun the script."
        )
    info(f"  verified: bucket '{bucket}' is empty")


def main() -> None:
    info("Scout canonical rewrite: Phase 0 quiesce verification")
    info("Spec: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md Section 6")

    # Env var pre-flight. Fail fast.
    db_url = require_env("SCOUT_DATABASE_URL")
    api_url = os.environ.get("SCOUT_API_URL", DEFAULT_API_URL).strip() or DEFAULT_API_URL
    supabase_url = require_env("SCOUT_SUPABASE_URL")
    service_role_key = require_env("SCOUT_SUPABASE_SERVICE_ROLE_KEY")
    bucket = os.environ.get("SCOUT_SUPABASE_STORAGE_BUCKET", DEFAULT_BUCKET).strip() or DEFAULT_BUCKET
    info(f"  API:      {api_url}")
    info(f"  DB:       {db_url.split('@')[-1] if '@' in db_url else '(hidden)'}")
    info(f"  Supabase: {supabase_url}  bucket={bucket}")

    # Step 1 - smoke-test API and DB reachability.
    info("")
    info("Step 1 / 5 - smoke-test connectivity")
    ready = read_ready(api_url)
    info(f"  /ready snapshot: {ready}")
    engine = create_engine(db_url, future=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1")).scalar_one()
    info("  DB reachable")

    # Step 2 - prompt operator to flip env vars in Railway dashboard.
    info("")
    info("Step 2 / 5 - operator flips env vars on Railway")
    print(
        "\n"
        "  Please set these three env vars on Railway for the backend service:\n"
        "    SCOUT_SCHEDULER_ENABLED=false\n"
        "    SCOUT_ENABLE_BOOTSTRAP=true\n"
        "    SCOUT_ENABLE_AI=false\n"
        "  Wait for Railway to redeploy and return /health 200, THEN continue."
    )
    prompt_enter("\n  Press Enter when all three are set and the backend has redeployed... ")

    # Step 3 - verify bootstrap + ai via /ready.
    info("")
    info("Step 3 / 5 - verify SCOUT_ENABLE_BOOTSTRAP and SCOUT_ENABLE_AI landed")
    verify_bootstrap_and_ai(api_url)

    # Step 4 - scheduler idle poll. This needs the operator to have flipped
    # SCOUT_SCHEDULER_ENABLED in Step 2 as well. We prompt a second time
    # to guard against a stale confirmation from Step 2 (which touched
    # multiple vars at once; a slow dashboard flip could race the poll).
    info("")
    info("Step 4 / 5 - scheduler idle verification (5-minute DB poll)")
    print(
        "\n"
        "  Re-confirm SCOUT_SCHEDULER_ENABLED=false is set on Railway and the\n"
        "  backend has fully redeployed. If any new scheduler tick fires during\n"
        "  the next 5 minutes, this verification will fail and you'll need to\n"
        "  investigate. The current tick (if one is mid-flight) must finish\n"
        "  before continuing."
    )
    prompt_enter("\n  Press Enter to begin the 5-minute idle poll... ")
    poll_scheduler_idle(db_url)

    # Step 5 - purge Supabase Storage bucket.
    info("")
    info("Step 5 / 5 - purge Supabase Storage attachments bucket")
    purge_supabase_bucket(supabase_url, service_role_key, bucket)

    info("")
    info("QUIESCE COMPLETE.")
    info("  Next steps per v5.1 plan:")
    info("  1. Close all scout-ui clients (mobile, web tabs) if you have not already.")
    info("  2. Update the Phase 0 handoff doc with the confirmation.")
    info("  3. Proceed to Phase 1 PR 1.1 (drop DB objects depending on legacy public.* tables).")
    sys.exit(0)


if __name__ == "__main__":
    main()
