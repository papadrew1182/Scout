"""Phase 5 unquiesce verification for the canonical rewrite sprint.

Companion doc: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
               Phase 5 PR 5.2 (--ai-only) and PR 5.3 (--full).

Verify-only for Railway env vars. Andrew flips env vars manually via the
Railway dashboard; this script confirms the flips landed.

Usage:

    # Phase 5 PR 5.2 partial re-enable (AI only):
    SCOUT_API_URL=https://... python scripts/unquiesce_prod.py --ai-only

    # Phase 5 PR 5.3 full re-enable (scheduler + bootstrap-off):
    SCOUT_DATABASE_URL=postgresql://... \\
    SCOUT_API_URL=https://... python scripts/unquiesce_prod.py --full

Exactly one flag required. --ai-only and --full together = reject.

Flag semantics:

    --ai-only
        Prompt operator to set SCOUT_ENABLE_AI=true on Railway.
        Wait for Enter.
        Poll /ready until ai_available=true (with timeout).

    --full
        Prompt operator to set SCOUT_SCHEDULER_ENABLED=true AND
        SCOUT_ENABLE_BOOTSTRAP=false on Railway.
        Wait for Enter.
        Verify /ready shows bootstrap_enabled=false.
        Poll public.scout_scheduled_runs for up to 6 minutes:
          - status='success' with created_at > baseline = healthy tick, pass
          - status='error' with created_at > baseline = failed tick, fail
            and surface the error column
          - status='skipped' = does not count, keep polling

Idempotent. Running twice is fine; each run re-prompts and re-verifies.

Non-goals:
    - Does NOT set Railway env vars. Operator does that via dashboard.
    - Does NOT reprovision smoke accounts. See scripts/provision_smoke_*.py.
    - Does NOT re-enable the smoke-deployed CI auto-trigger. That is the
      PR 5.3 ci.yml edit (per reenable checklist section 2).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import requests
from sqlalchemy import create_engine, text

DEFAULT_API_URL = "https://scout-backend-production-9991.up.railway.app"

# How long we wait for /ready to reflect new env state after a redeploy.
READY_POLL_TIMEOUT_SECONDS = 90
READY_POLL_STEP_SECONDS = 5

# How long we wait for the first scheduler tick after re-enable.
# The tick interval is 5 minutes; we allow a bit of slack for deploy + start.
SCHEDULER_TICK_TIMEOUT_SECONDS = 6 * 60
SCHEDULER_POLL_STEP_SECONDS = 15


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"[unquiesce] {msg}")


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
    return {}  # unreachable


def prompt_enter(message: str) -> None:
    sys.stdout.write(message)
    sys.stdout.flush()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        fail("Aborted by operator.")


def poll_ready_until(
    api_url: str, field: str, expected_value: object, timeout_s: int = READY_POLL_TIMEOUT_SECONDS
) -> None:
    """Poll /ready until `field` equals `expected_value`. Fails on timeout."""
    info(f"Polling /ready for {field}={expected_value} (timeout {timeout_s}s)...")
    deadline = time.monotonic() + timeout_s
    last: object = None
    while time.monotonic() < deadline:
        ready = read_ready(api_url)
        value = ready.get(field)
        if value == expected_value:
            info(f"  verified: /ready.{field} = {value}")
            return
        if value != last:
            info(f"  current /ready.{field} = {value}")
            last = value
        time.sleep(READY_POLL_STEP_SECONDS)
    fail(
        f"Timed out after {timeout_s}s: /ready.{field} expected {expected_value}, last saw {last}. "
        "Confirm the env var is set on Railway and the backend has fully redeployed."
    )


def poll_for_healthy_tick(db_url: str) -> None:
    """Poll public.scout_scheduled_runs for a complete, healthy tick.

    Schema (migration 016, verified 2026-04-23):
      id, job_name, family_id, member_id, run_date,
      status (CHECK IN 'success','error','skipped'),
      duration_ms, result, error, created_at

    Healthy tick = a row with created_at > baseline AND status = 'success'.
    Failed tick = a row with created_at > baseline AND status = 'error'
      (surface the error column and fail verification).
    Skipped row = status = 'skipped'. Does NOT count as healthy;
      keep polling until a success lands or the deadline passes.
    """
    info(
        f"Polling public.scout_scheduled_runs for up to "
        f"{SCHEDULER_TICK_TIMEOUT_SECONDS // 60} minutes to confirm scheduler active..."
    )
    baseline_ts = datetime.now(timezone.utc)
    engine = create_engine(db_url, future=True)
    deadline = time.monotonic() + SCHEDULER_TICK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            # Errors fail immediately - the scheduler ran but work broke.
            errors = conn.execute(
                text(
                    "SELECT job_name, error, created_at "
                    "FROM public.scout_scheduled_runs "
                    "WHERE created_at > :baseline "
                    "  AND status = 'error' "
                    "ORDER BY created_at ASC"
                ),
                {"baseline": baseline_ts},
            ).mappings().all()
            success_count = conn.execute(
                text(
                    "SELECT count(*) FROM public.scout_scheduled_runs "
                    "WHERE created_at > :baseline AND status = 'success'"
                ),
                {"baseline": baseline_ts},
            ).scalar_one()
            skipped_count = conn.execute(
                text(
                    "SELECT count(*) FROM public.scout_scheduled_runs "
                    "WHERE created_at > :baseline AND status = 'skipped'"
                ),
                {"baseline": baseline_ts},
            ).scalar_one()
        elapsed = int(time.monotonic() - (deadline - SCHEDULER_TICK_TIMEOUT_SECONDS))
        info(
            f"  elapsed={elapsed}s, success={success_count}, "
            f"error={len(errors)}, skipped={skipped_count}"
        )
        if errors:
            detail = "\n".join(
                f"  - {r['job_name']} at {r['created_at']}: {r['error'] or '(no error text)'}"
                for r in errors
            )
            fail(
                f"Scheduler ran but {len(errors)} tick(s) errored after baseline "
                f"{baseline_ts.isoformat()}:\n{detail}"
            )
        if success_count >= 1:
            info(f"  verified: {success_count} healthy scheduler tick(s) observed")
            return
        # success_count == 0 and no errors: either no ticks yet or only
        # skipped rows. Keep waiting for a success.
        time.sleep(SCHEDULER_POLL_STEP_SECONDS)
    fail(
        f"Timed out after {SCHEDULER_TICK_TIMEOUT_SECONDS // 60} minutes waiting for a "
        f"successful scheduler tick (status='success') since baseline "
        f"{baseline_ts.isoformat()}. Either the scheduler is not running, or every "
        "tick in the window resolved to status='skipped'. Check Railway logs and "
        "SCOUT_SCHEDULER_ENABLED."
    )


def run_ai_only(api_url: str) -> None:
    info("Mode: --ai-only (Phase 5 PR 5.2 partial re-enable)")
    # Pre-state: record current /ready for reference.
    before = read_ready(api_url)
    info(f"  /ready before: ai_available={before.get('ai_available')}")
    print(
        "\n"
        "  On Railway, set SCOUT_ENABLE_AI=true for the backend service.\n"
        "  Do NOT touch SCOUT_SCHEDULER_ENABLED or SCOUT_ENABLE_BOOTSTRAP yet.\n"
        "  Wait for Railway to redeploy and return /health 200, THEN continue."
    )
    prompt_enter("\n  Press Enter when SCOUT_ENABLE_AI=true is set and the backend has redeployed... ")
    poll_ready_until(api_url, "ai_available", True)
    info("")
    info("AI re-enable verified.")
    info("  Next step per v5.1 Phase 5 Step 7: run Part B acceptance checklist.")


def run_full(api_url: str, db_url: str) -> None:
    info("Mode: --full (Phase 5 PR 5.3 full re-enable)")
    # Pre-state.
    before = read_ready(api_url)
    info(f"  /ready before: bootstrap_enabled={before.get('bootstrap_enabled')}")
    print(
        "\n"
        "  On Railway, set these two env vars for the backend service:\n"
        "    SCOUT_SCHEDULER_ENABLED=true  (or delete it; default is true)\n"
        "    SCOUT_ENABLE_BOOTSTRAP=false\n"
        "  Do NOT change SCOUT_ENABLE_AI here; --ai-only already handled that.\n"
        "  Wait for Railway to redeploy and return /health 200, THEN continue."
    )
    prompt_enter(
        "\n  Press Enter when both env vars are set and the backend has redeployed... "
    )
    # Bootstrap verification first (fast, via /ready).
    poll_ready_until(api_url, "bootstrap_enabled", False)
    # Scheduler verification (slow, requires a tick to happen).
    info("")
    poll_for_healthy_tick(db_url)
    info("")
    info("Full re-enable verified.")
    info("  Next step per v5.1 Phase 5 Step 8:")
    info("  1. Reprovision smoke accounts (scripts/provision_smoke_child.py + adult).")
    info("  2. Merge the PR that re-enables smoke-deployed auto-trigger in .github/workflows/ci.yml.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Phase 5 unquiesce flips landed on Railway.",
        epilog="Exactly one of --ai-only or --full is required.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--ai-only",
        action="store_true",
        help="Phase 5 PR 5.2. Verifies SCOUT_ENABLE_AI=true reflected in /ready.ai_available.",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help=(
            "Phase 5 PR 5.3. Verifies SCOUT_SCHEDULER_ENABLED=true (healthy tick in DB) "
            "AND SCOUT_ENABLE_BOOTSTRAP=false (/ready.bootstrap_enabled)."
        ),
    )
    args = parser.parse_args()

    info("Scout canonical rewrite: Phase 5 unquiesce verification")
    info("Spec: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md Phase 5")

    api_url = os.environ.get("SCOUT_API_URL", DEFAULT_API_URL).strip() or DEFAULT_API_URL
    info(f"  API: {api_url}")

    if args.ai_only:
        # --ai-only does NOT need DB access. AI verification is /ready only.
        run_ai_only(api_url)
    elif args.full:
        db_url = require_env("SCOUT_DATABASE_URL")
        info(f"  DB:  {db_url.split('@')[-1] if '@' in db_url else '(hidden)'}")
        run_full(api_url, db_url)
    else:
        # Belt-and-suspenders: argparse mutually_exclusive already rejects,
        # but defense in depth in case of future edits.
        fail("Exactly one of --ai-only or --full is required.")


if __name__ == "__main__":
    main()
