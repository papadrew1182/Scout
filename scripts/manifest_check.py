"""Canonical rewrite manifest checker.

Companion doc: docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md
               §6 PR 2.0 gate.

Verifies that the production database and the repository file tree match
the post-PR-1.4 contract documented in the manifest. Exits 0 if every
check passes; exits 1 if any check fails.

Four checks:

  1. Public schema base tables. Expected exactly:
       _scout_migrations, sessions, scout_scheduled_runs

  2. Scout schema base tables. Expected exactly the 53 retained tables
     from manifest §1.2 (i.e. all rows whose Phase 1 disposition is
     "truncated in 056; retained", excluding the five dropped in 055).

  3. Scout views dropped by migration 053 are absent. Two views
     intentionally retained by 053 (v_calendar_publication and
     v_control_plane) must still be present.

  4. Migrations 053..057 are byte-mirrored in `backend/migrations/` and
     `database/migrations/`. SHA-256 must match per file.

Connectivity:

  Reads SCOUT_DATABASE_URL (preferred) or DATABASE_URL. Matches the
  convention used by backend/migrate.py and scripts/quiesce_prod.py.

Optional snapshot output:

  --write-snapshot PATH writes a raw schema-introspection capture to
  PATH. The capture covers the four queries listed in manifest §9 plus
  the migration mirror manifest. Use this to produce
  docs/plans/runtime/<date>/prod_schema_snapshot.txt.

Usage:

  SCOUT_DATABASE_URL=postgresql://... python scripts/manifest_check.py
  SCOUT_DATABASE_URL=postgresql://... python scripts/manifest_check.py \\
      --write-snapshot docs/plans/runtime/2026-04-25/prod_schema_snapshot.txt
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras


# Manifest v1.1 §1.1 - the only public.* base tables that survive 057.
EXPECTED_PUBLIC_TABLES = frozenset({
    "_scout_migrations",
    "sessions",
    "scout_scheduled_runs",
})

# Manifest v1.1 §1.2 - 53 scout.* base tables retained after Phase 1.
# Excludes the five tables dropped in 055: meal_transformations,
# routine_steps, routine_templates, task_occurrences, task_templates.
EXPECTED_SCOUT_TABLES = frozenset({
    "activity_events",
    "affirmation_delivery_log",
    "affirmation_feedback",
    "affirmations",
    "allowance_periods",
    "allowance_results",
    "bill_snapshots",
    "budget_snapshots",
    "calendar_exports",
    "connector_accounts",
    "connector_event_log",
    "connectors",
    "daily_win_results",
    "device_registrations",
    "external_calendar_events",
    "greenlight_exports",
    "home_assets",
    "home_zones",
    "household_rules",
    "maintenance_instances",
    "maintenance_templates",
    "nudge_dispatch_items",
    "nudge_dispatches",
    "nudge_rules",
    "permissions",
    "project_budget_entries",
    "project_milestones",
    "project_tasks",
    "project_template_tasks",
    "project_templates",
    "projects",
    "push_deliveries",
    "push_devices",
    "quiet_hours_family",
    "reward_extras_catalog",
    "reward_ledger_entries",
    "reward_policies",
    "role_tier_permissions",
    "settlement_batches",
    "stale_data_alerts",
    "standards_of_done",
    "sync_cursors",
    "sync_jobs",
    "sync_runs",
    "task_assignment_rules",
    "task_completions",
    "task_exceptions",
    "task_notes",
    "time_blocks",
    "travel_estimates",
    "user_family_memberships",
    "user_preferences",
    "work_context_events",
})

# Migration 053 drops exactly these 10 scout views.
SCOUT_VIEWS_DROPPED_BY_053 = frozenset({
    "families",
    "family_members",
    "user_accounts",
    "sessions",
    "role_tiers",
    "role_tier_overrides",
    "connector_mappings",
    "connector_configs",
    "v_household_today",
    "v_rewards_current_week",
})

# Per migration 053 comment block: these scout views reference only
# retained scout.* tables and must remain present.
SCOUT_VIEWS_RETAINED = frozenset({
    "v_calendar_publication",
    "v_control_plane",
})

# Phase 1 migration filenames.
PHASE_1_MIGRATIONS = (
    "053_phase1_drop_dependent_views.sql",
    "054_phase1_drop_fks_on_retained.sql",
    "055_phase1_drop_scout_rebuilt.sql",
    "056_phase1_truncate_domain_data.sql",
    "057_phase1_drop_public_legacy.sql",
)


# ----- Output helpers --------------------------------------------------------


class CheckResult:
    """One check's pass/fail with a list of human-readable detail lines."""

    def __init__(self, name: str, passed: bool, details: list[str]) -> None:
        self.name = name
        self.passed = passed
        self.details = details

    def render(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] {self.name}"]
        lines.extend(f"    {line}" for line in self.details)
        return "\n".join(lines)


def fail_exit(msg: str) -> "ResultsExit":
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(2)


# ----- DB queries ------------------------------------------------------------


def get_db_url() -> str:
    url = os.environ.get("SCOUT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        fail_exit("Neither SCOUT_DATABASE_URL nor DATABASE_URL is set.")
    return url


def query_tables(cur, schema: str) -> set[str]:
    """All non-system base tables in `schema`."""
    cur.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = %s
          AND tablename NOT LIKE 'pg_%%'
        ORDER BY tablename
        """,
        (schema,),
    )
    return {row[0] for row in cur.fetchall()}


def query_views(cur, schema: str) -> set[str]:
    cur.execute(
        """
        SELECT viewname
        FROM pg_views
        WHERE schemaname = %s
        ORDER BY viewname
        """,
        (schema,),
    )
    return {row[0] for row in cur.fetchall()}


def query_fks(cur) -> list[tuple[str, str, str, str, str, str, str]]:
    """All FOREIGN KEY constraints whose source or target lives in scout/public.

    Returns rows of:
      (constraint_name, source_schema, source_table, source_columns,
       target_schema, target_table, target_columns)
    """
    cur.execute(
        """
        SELECT
            con.conname,
            ns_src.nspname AS src_schema,
            cls_src.relname AS src_table,
            (
                SELECT string_agg(att.attname, ',' ORDER BY u.ord)
                FROM unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord)
                JOIN pg_attribute att
                  ON att.attrelid = cls_src.oid AND att.attnum = u.attnum
            ) AS src_cols,
            ns_tgt.nspname AS tgt_schema,
            cls_tgt.relname AS tgt_table,
            (
                SELECT string_agg(att.attname, ',' ORDER BY u.ord)
                FROM unnest(con.confkey) WITH ORDINALITY AS u(attnum, ord)
                JOIN pg_attribute att
                  ON att.attrelid = cls_tgt.oid AND att.attnum = u.attnum
            ) AS tgt_cols
        FROM pg_constraint con
        JOIN pg_class cls_src ON cls_src.oid = con.conrelid
        JOIN pg_namespace ns_src ON ns_src.oid = cls_src.relnamespace
        JOIN pg_class cls_tgt ON cls_tgt.oid = con.confrelid
        JOIN pg_namespace ns_tgt ON ns_tgt.oid = cls_tgt.relnamespace
        WHERE con.contype = 'f'
          AND (ns_src.nspname IN ('public', 'scout')
               OR ns_tgt.nspname IN ('public', 'scout'))
        ORDER BY ns_src.nspname, cls_src.relname, con.conname
        """,
    )
    return list(cur.fetchall())


def query_migrations_table(cur) -> list[tuple[str, str]]:
    cur.execute(
        """
        SELECT filename, applied_at::text
        FROM public._scout_migrations
        ORDER BY filename
        """,
    )
    return list(cur.fetchall())


# ----- Checks ----------------------------------------------------------------


def check_public_tables(cur) -> CheckResult:
    actual = query_tables(cur, "public")
    extra = actual - EXPECTED_PUBLIC_TABLES
    missing = EXPECTED_PUBLIC_TABLES - actual
    details = [f"expected: {sorted(EXPECTED_PUBLIC_TABLES)}",
               f"actual:   {sorted(actual)}"]
    if missing:
        details.append(f"MISSING (must exist): {sorted(missing)}")
    if extra:
        details.append(f"UNEXPECTED (should be dropped): {sorted(extra)}")
    return CheckResult(
        "Public schema base-table set matches manifest §1.1",
        passed=(not missing and not extra),
        details=details,
    )


def check_scout_tables(cur) -> CheckResult:
    actual = query_tables(cur, "scout")
    extra = actual - EXPECTED_SCOUT_TABLES
    missing = EXPECTED_SCOUT_TABLES - actual
    details = [
        f"expected count: {len(EXPECTED_SCOUT_TABLES)}",
        f"actual count:   {len(actual)}",
    ]
    if missing:
        details.append(f"MISSING (manifest §1.2 retained, not in DB): {sorted(missing)}")
    if extra:
        details.append(f"UNEXPECTED (in DB, not in manifest §1.2 retained): {sorted(extra)}")
    return CheckResult(
        "Scout schema retained-table set matches manifest §1.2",
        passed=(not missing and not extra),
        details=details,
    )


def check_dropped_views_absent(cur) -> CheckResult:
    actual_views = query_views(cur, "scout")
    still_present = SCOUT_VIEWS_DROPPED_BY_053 & actual_views
    retained_missing = SCOUT_VIEWS_RETAINED - actual_views
    details = [
        f"views that 053 must drop: {sorted(SCOUT_VIEWS_DROPPED_BY_053)}",
        f"views retained per 053:   {sorted(SCOUT_VIEWS_RETAINED)}",
        f"actual scout views:       {sorted(actual_views)}",
    ]
    if still_present:
        details.append(f"DROPPED VIEW STILL PRESENT: {sorted(still_present)}")
    if retained_missing:
        details.append(f"RETAINED VIEW MISSING: {sorted(retained_missing)}")
    return CheckResult(
        "Migration 053's dropped scout views are absent; retained ones present",
        passed=(not still_present and not retained_missing),
        details=details,
    )


def check_migrations_mirrored(repo_root: Path) -> CheckResult:
    backend_dir = repo_root / "backend" / "migrations"
    database_dir = repo_root / "database" / "migrations"
    failures: list[str] = []
    summaries: list[str] = []
    for fname in PHASE_1_MIGRATIONS:
        b = backend_dir / fname
        d = database_dir / fname
        b_exists = b.is_file()
        d_exists = d.is_file()
        if not b_exists or not d_exists:
            failures.append(
                f"{fname}: backend={b_exists}, database={d_exists}"
            )
            continue
        b_hash = hashlib.sha256(b.read_bytes()).hexdigest()
        d_hash = hashlib.sha256(d.read_bytes()).hexdigest()
        if b_hash != d_hash:
            failures.append(
                f"{fname}: hash mismatch  backend={b_hash[:12]}  database={d_hash[:12]}"
            )
        else:
            summaries.append(f"{fname}: sha256={b_hash[:12]} (mirrored)")
    details = summaries + ([f"FAILURES: {len(failures)}"] + failures if failures else [])
    return CheckResult(
        "Phase 1 migrations 053..057 byte-mirrored across backend/ and database/",
        passed=not failures,
        details=details,
    )


# ----- Snapshot writer -------------------------------------------------------


def write_snapshot(cur, repo_root: Path, out_path: Path) -> None:
    public_tables = sorted(query_tables(cur, "public"))
    scout_tables = sorted(query_tables(cur, "scout"))
    public_views = sorted(query_views(cur, "public"))
    scout_views = sorted(query_views(cur, "scout"))
    fks = query_fks(cur)
    migrations = query_migrations_table(cur)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("Scout canonical rewrite - prod schema snapshot")
    lines.append("Generated by scripts/manifest_check.py --write-snapshot")
    lines.append("")
    lines.append(f"public schema base tables ({len(public_tables)}):")
    for t in public_tables:
        lines.append(f"  - public.{t}")
    lines.append("")
    lines.append(f"scout schema base tables ({len(scout_tables)}):")
    for t in scout_tables:
        lines.append(f"  - scout.{t}")
    lines.append("")
    lines.append(f"public schema views ({len(public_views)}):")
    for v in public_views:
        lines.append(f"  - public.{v}")
    lines.append("")
    lines.append(f"scout schema views ({len(scout_views)}):")
    for v in scout_views:
        lines.append(f"  - scout.{v}")
    lines.append("")
    lines.append(f"foreign keys touching public/scout ({len(fks)}):")
    for conname, src_ns, src_tbl, src_cols, tgt_ns, tgt_tbl, tgt_cols in fks:
        lines.append(
            f"  - {conname}: {src_ns}.{src_tbl}({src_cols}) -> {tgt_ns}.{tgt_tbl}({tgt_cols})"
        )
    lines.append("")
    lines.append(f"public._scout_migrations rows ({len(migrations)}):")
    for fname, applied in migrations:
        lines.append(f"  - {fname}  applied_at={applied}")
    lines.append("")
    lines.append("Phase 1 migration mirror manifest:")
    backend_dir = repo_root / "backend" / "migrations"
    database_dir = repo_root / "database" / "migrations"
    for fname in PHASE_1_MIGRATIONS:
        b = backend_dir / fname
        d = database_dir / fname
        bh = hashlib.sha256(b.read_bytes()).hexdigest() if b.is_file() else "MISSING"
        dh = hashlib.sha256(d.read_bytes()).hexdigest() if d.is_file() else "MISSING"
        match = "match" if bh == dh and bh != "MISSING" else "MISMATCH"
        lines.append(f"  - {fname}  backend={bh[:16]}  database={dh[:16]}  {match}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----- Main ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify prod DB and repo against manifest v1.1.")
    parser.add_argument(
        "--write-snapshot",
        type=Path,
        default=None,
        help="If set, write a raw schema introspection snapshot to this path.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    db_url = get_db_url()

    print("Scout canonical rewrite manifest checker")
    print(f"Manifest: docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md")
    print(f"Repo root: {repo_root}")
    print(f"DB host:   {db_url.split('@')[-1].split('/')[0] if '@' in db_url else '(hidden)'}")
    print("")

    results: list[CheckResult] = []

    # File-tree check first - no DB needed.
    results.append(check_migrations_mirrored(repo_root))

    # DB checks.
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.Error as exc:
        fail_exit(f"Could not connect to database: {exc}")
    try:
        with conn.cursor() as cur:
            results.append(check_public_tables(cur))
            results.append(check_scout_tables(cur))
            results.append(check_dropped_views_absent(cur))

            if args.write_snapshot is not None:
                write_snapshot(cur, repo_root, args.write_snapshot)
                print(f"Schema snapshot written: {args.write_snapshot}")
                print("")
    finally:
        conn.close()

    print("=" * 72)
    for r in results:
        print(r.render())
    print("=" * 72)

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"FAILED: {len(failed)} of {len(results)} checks did not pass")
        sys.exit(1)
    print(f"PASSED: all {len(results)} checks")
    sys.exit(0)


if __name__ == "__main__":
    main()
