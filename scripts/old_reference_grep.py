"""Grep for unqualified references to dropped public.* tables.

Companion doc: docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md
               §6 PR 2.0 gate, §3 consumer manifest, §4 intermediate-state
               resolver.

Why this exists:
    After migration 057, 39 public.* base tables are gone. The remaining
    code may still reference them as `families`, `family_members`, etc.
    Once Phase 2 PR 2.1 creates `scout.families`, `scout.family_members`,
    those unqualified references will silently resolve via the schema
    search-path against the new scout.* tables - "search-path
    resurrection." Every such reference must be mapped to a §3 consumer
    manifest owner so PR 3.x rewires it explicitly.

What this script does:
    Walks the file trees listed below and emits a JSON report of every
    line where one of the 39 dropped public.* table names appears as an
    unqualified identifier (word boundary; not preceded by `.` or a
    word character).

    Schema-qualified references (e.g. `public.families`, `scout.families`)
    are excluded by the leading lookbehind in the regex.

    Each hit is mapped to its owner row in manifest §3 (Consumer
    manifest). The script parses §3 at startup, builds an
    exact-path -> section-id index, and tags each hit with the owner
    string `"§3.X <relpath>"`. Hits whose file path is not listed in §3
    are tagged `"UNMAPPED"`. Per the PR 2.0 §6 gate, the presence of any
    UNMAPPED hits is a hard fail.

Scope:
    Per Andrew's PR 2.0 brief: backend/, scripts/, tests/, scout-ui/,
    smoke-tests/, .github/workflows/.

    The two PR 2.0 gate scripts (manifest_check.py and old_reference_grep.py)
    are self-excluded - their expected-set definitions reference the dropped
    table names by design and are not consumers.

    Migration files 001..057 in backend/migrations/ are excluded.
    Justification: migration files reference dropped tables by definition
    (they created or dropped them); they do not represent consumer code
    requiring Phase 3 rewire. Future migrations 058+ remain in scope
    because new migrations should use qualified scout.* names per the
    manifest's canonical conventions. database/migrations/ is excluded
    defensively (mirrored from backend/ - same content, no separate
    consumers).

    The following directories and extensions are scoped out of manifest
    §3 by design and are excluded from the grep:

      - scout-ui/app/**, scout-ui/components/**, scout-ui/features/**
        UI render layer. Consumes the API client (scout-ui/lib/*) which
        IS in §3.7; never touches the DB directly. Table-name string
        hits in these files are React state-variable names (e.g.
        `const [events, setEvents] = useState<Event[]>([])`) and JSX
        labels - structural false positives.

      - backend/app/schemas/**
        Pydantic request/response shapes. Field names like `notes:
        str | None` collide with table names by coincidence; these
        files do not query the DB.

      - *.json
        Config files. Hits are typically natural-language strings
        (e.g. iOS permission descriptions in scout-ui/app.json).

      - *.md
        Documentation files. Hits are prose mentions of table names
        in module-level docstrings or README content.

Usage:
    python scripts/old_reference_grep.py
    python scripts/old_reference_grep.py --out path/to/output.json
    python scripts/old_reference_grep.py --manifest path/to/manifest.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path


# Manifest v1.1 §1.1: every public.* base table dropped in migration 057.
# Excludes the three retained: _scout_migrations, sessions, scout_scheduled_runs.
DROPPED_PUBLIC_TABLES: tuple[str, ...] = (
    "activity_records",
    "ai_conversations",
    "ai_daily_insights",
    "ai_homework_sessions",
    "ai_messages",
    "ai_tool_audit",
    "allowance_ledger",
    "bills",
    "chore_templates",
    "connector_configs",
    "connector_mappings",
    "daily_wins",
    "dietary_preferences",
    "event_attendees",
    "events",
    "families",
    "family_members",
    "family_memories",
    "grocery_items",
    "health_summaries",
    "meal_plans",
    "meal_reviews",
    "meals",
    "member_config",
    "notes",
    "parent_action_items",
    "personal_tasks",
    "planner_bundle_applies",
    "purchase_requests",
    "role_tier_overrides",
    "role_tiers",
    "routine_steps",
    "routines",
    "scout_anomaly_suppressions",
    "scout_mcp_tokens",
    "task_instance_step_completions",
    "task_instances",
    "user_accounts",
    "weekly_meal_plans",
)

# Roots to walk, relative to repo root.
SCAN_PATHS: tuple[str, ...] = (
    "backend",
    "scripts",
    "tests",
    "scout-ui",
    "smoke-tests",
    ".github/workflows",
)

# File extensions to scan. Plain-text only; the grep is identifier-based,
# so extension diversity is fine.
# .json and .md are intentionally excluded - they're config/docs that
# consume natural-language mentions of table names, not DB references.
# See module docstring "scoped out of manifest §3 by design" for the
# full justification.
SCANNED_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".sql", ".ts", ".tsx", ".js", ".jsx",
    ".yml", ".yaml", ".txt", ".toml", ".ini", ".cfg",
    ".sh", ".bash", ".env", ".dockerfile", ".html", ".css",
})

# Directory prefixes (relative to repo root) excluded from the scan
# because they're scoped out of manifest §3 by design.
EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "scout-ui/app/",
    "scout-ui/components/",
    "scout-ui/features/",
    "backend/app/schemas/",
)

# Directory-name fragments to skip while walking. Match anywhere in path.
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "env", "dist", "build", ".next", "out",
    "coverage", ".turbo", ".cache",
})

# Specific files self-excluded: this script and the manifest checker
# legitimately enumerate the dropped table names as expected-set
# definitions, not as consumers.
EXCLUDED_FILES: frozenset[str] = frozenset({
    "scripts/manifest_check.py",
    "scripts/old_reference_grep.py",
})

# Truncate each captured line to this many chars so the JSON stays
# readable on pathological lines (e.g. a long SQL string literal).
LINE_TEXT_TRUNCATE = 240

# Default manifest path, relative to repo root.
DEFAULT_MANIFEST_REL = "docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md"

# Highest pre-canonical-rewrite migration number. Migrations 001..057
# created or dropped the legacy public.* tables; references in those
# files are expected and do not represent consumer code.
MAX_EXCLUDED_MIGRATION = 57

# Regex: paths inside backend/migrations/ named NNN[suffix]_*.sql where
# NNN is the 3-digit number and an optional single letter suffix is
# allowed for split migrations (e.g. 046a_push_notifications.sql,
# 046b_ai_conversation_resume.sql). The numeric range check is applied
# separately so the constant above stays the only place to bump on a
# future Phase-1.X migration cycle.
_MIGRATION_PATH_RE = re.compile(r"^backend/migrations/(\d{3})[a-z]?_[^/]*\.sql$")

# Owner-mapping markers.
OWNER_UNMAPPED = "UNMAPPED"


def build_pattern() -> re.Pattern[str]:
    """Match a dropped table name as an unqualified identifier.

    `(?<![.\\w])` is the key: excludes `public.families`, `scout.families`,
    `_families`, and `myfamilies` (would not match anyway under \\b but
    belt and suspenders against partial-word matches).

    `\\b` after the alternation closes the right boundary so `families_old`
    does not match.

    Case-insensitive: SQL is case-insensitive at the language level;
    being lenient here surfaces hits like `FAMILIES` in macros/upper-cased
    SQL.
    """
    alt = "|".join(re.escape(name) for name in DROPPED_PUBLIC_TABLES)
    return re.compile(rf"(?<![.\w])(?P<name>{alt})\b", re.IGNORECASE)


def is_excluded_dir(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def is_excluded_migration(rel_path: str) -> bool:
    """True for backend/migrations/0NN_*.sql with NN <= 57.

    Andrew's PR 2.0 brief also names `database/migrations/` as excluded.
    That tree is not in SCAN_PATHS so it is not walked; the test below is
    defensive in case SCAN_PATHS is ever extended.
    """
    if rel_path.startswith("database/migrations/"):
        return True
    m = _MIGRATION_PATH_RE.match(rel_path)
    if m is None:
        return False
    return 1 <= int(m.group(1)) <= MAX_EXCLUDED_MIGRATION


def iter_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for scan in SCAN_PATHS:
        root = repo_root / scan
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
            for fname in filenames:
                p = Path(dirpath) / fname
                if is_excluded_dir(p):
                    continue
                rel = p.relative_to(repo_root).as_posix()
                if rel in EXCLUDED_FILES:
                    continue
                if is_excluded_migration(rel):
                    continue
                if any(rel.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
                    continue
                if p.suffix.lower() in SCANNED_EXTENSIONS or fname.lower() in {
                    "dockerfile", "makefile", "procfile",
                }:
                    files.append(p)
    return files


# --- Manifest §3 parser ------------------------------------------------------

# A "file-path-looking" first column. The §3 first column is one of:
#   - bare file path:        `backend/start.sh`, `scout-ui/lib/api.ts`
#   - path with suffix word: `backend/app/main.py lifespan`
#   - URL route:             `GET /health`
#   - function name:         `start_scheduler / _tick`
# We accept the first whitespace-delimited token if it matches the pattern
# below (looks like a relative repo path with a recognizable extension or
# any path containing `/`). URL routes and function names are skipped.
_PATH_RE = re.compile(
    r"^[\w./-]+(?:\.(?:py|ts|tsx|js|jsx|sql|sh|spec\.ts|yml|yaml|md|txt|toml))$",
    re.IGNORECASE,
)


def parse_manifest_section_3(manifest_path: Path) -> tuple[dict[str, list[tuple[str, int]]], list[str]]:
    """Parse manifest §3 into {file_path: [(section_id, line_number)]}.

    Returns the index plus a list of warnings (e.g. duplicate file paths
    across subsections). The script does not de-dup automatically; the
    first parsed occurrence wins for owner-string formatting, but
    duplicates are surfaced in the report.
    """
    text = manifest_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    section_3_re = re.compile(r"^##\s+3\.\s")
    section_4_re = re.compile(r"^##\s+4\.\s")
    subsection_re = re.compile(r"^###\s+3\.(\d+)\b")
    table_data_re = re.compile(r"^\|\s*(.+?)\s*\|")
    table_separator_re = re.compile(r"^\|\s*-+")

    in_section_3 = False
    current_subsection: str | None = None
    in_table_body = False
    last_was_separator = False

    index: dict[str, list[tuple[str, int]]] = {}
    warnings: list[str] = []

    for lineno, line in enumerate(lines, start=1):
        if section_3_re.match(line):
            in_section_3 = True
            continue
        if section_4_re.match(line):
            in_section_3 = False
            continue
        if not in_section_3:
            continue

        sub_match = subsection_re.match(line)
        if sub_match:
            current_subsection = f"3.{sub_match.group(1)}"
            in_table_body = False
            last_was_separator = False
            continue

        if not current_subsection:
            continue

        if table_separator_re.match(line):
            in_table_body = True
            last_was_separator = True
            continue

        if not in_table_body:
            continue

        if not line.startswith("|"):
            in_table_body = False
            continue

        m = table_data_re.match(line)
        if not m:
            continue
        col1 = m.group(1).strip()
        if not col1:
            continue

        first_token = col1.split()[0]
        if not _PATH_RE.match(first_token):
            continue

        rel = first_token.replace("\\", "/")
        owners = index.setdefault(rel, [])
        if owners:
            warnings.append(
                f"duplicate manifest §3 entry: {rel} appears in §{owners[0][0]} and §{current_subsection}"
            )
        owners.append((current_subsection, lineno))

    return index, warnings


def lookup_owner(rel_path: str, owner_index: dict[str, list[tuple[str, int]]]) -> str:
    """Return formatted owner string or OWNER_UNMAPPED."""
    owners = owner_index.get(rel_path)
    if not owners:
        return OWNER_UNMAPPED
    section_id, _line = owners[0]
    return f"§{section_id} {rel_path}"


# --- File scan ---------------------------------------------------------------


def scan_file(
    path: Path,
    pattern: re.Pattern[str],
    repo_root: Path,
    owner_index: dict[str, list[tuple[str, int]]],
) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    rel = path.relative_to(repo_root).as_posix()
    owner = lookup_owner(rel, owner_index)

    hits: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in pattern.finditer(line):
            captured = m.group("name")
            text_clip = line.strip()
            if len(text_clip) > LINE_TEXT_TRUNCATE:
                text_clip = text_clip[: LINE_TEXT_TRUNCATE - 3] + "..."
            hits.append({
                "file": rel,
                "line": lineno,
                "table": captured.lower(),
                "match": captured,
                "text": text_clip,
                "manifest_section_3_owner": owner,
            })
    return hits


def build_summary(hits: list[dict]) -> dict:
    files = {h["file"] for h in hits}
    by_table: dict[str, int] = {}
    by_section: dict[str, int] = {}
    unmapped_files: set[str] = set()
    for h in hits:
        by_table[h["table"]] = by_table.get(h["table"], 0) + 1
        owner = h["manifest_section_3_owner"]
        if owner == OWNER_UNMAPPED:
            unmapped_files.add(h["file"])
            section_key = OWNER_UNMAPPED
        else:
            section_key = owner.split()[0]  # e.g. "§3.6"
        by_section[section_key] = by_section.get(section_key, 0) + 1
    unmapped_hits = by_section.get(OWNER_UNMAPPED, 0)
    return {
        "total_hits": len(hits),
        "files_with_hits": len(files),
        "unmapped_hits": unmapped_hits,
        "unmapped_files_count": len(unmapped_files),
        "unmapped_files": sorted(unmapped_files),
        "tables_referenced": dict(sorted(by_table.items(), key=lambda kv: (-kv[1], kv[0]))),
        "hits_by_section": dict(sorted(by_section.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Grep for unqualified references to dropped public.* tables.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write JSON report to this path. If omitted, prints to stdout.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Path to canonical rewrite manifest. Defaults to v1.1 in docs/plans/.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = args.manifest if args.manifest else repo_root / DEFAULT_MANIFEST_REL
    if not manifest_path.is_file():
        print(f"FATAL: manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(2)

    owner_index, parse_warnings = parse_manifest_section_3(manifest_path)
    pattern = build_pattern()

    files = iter_files(repo_root)
    hits: list[dict] = []
    for f in files:
        hits.extend(scan_file(f, pattern, repo_root, owner_index))

    summary = build_summary(hits)

    report = {
        "scan_date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repo_root": repo_root.as_posix(),
        "manifest_path": manifest_path.relative_to(repo_root).as_posix() if manifest_path.is_relative_to(repo_root) else manifest_path.as_posix(),
        "scan_paths": list(SCAN_PATHS),
        "scanned_extensions": sorted(SCANNED_EXTENSIONS),
        "excluded_dir_names": sorted(EXCLUDED_DIR_NAMES),
        "excluded_files": sorted(EXCLUDED_FILES),
        "excluded_path_prefixes": list(EXCLUDED_PATH_PREFIXES),
        "excluded_migrations_through": MAX_EXCLUDED_MIGRATION,
        "dropped_public_tables": list(DROPPED_PUBLIC_TABLES),
        "manifest_section_3_files_indexed": len(owner_index),
        "manifest_parse_warnings": parse_warnings,
        "summary": summary,
        "hits": hits,
    }

    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
        gate_state = "FAIL" if summary["unmapped_hits"] > 0 else "PASS"
        print(
            f"[grep §6 PR 2.0 gate: {gate_state}] "
            f"hits={summary['total_hits']} files={summary['files_with_hits']} "
            f"unmapped_hits={summary['unmapped_hits']} unmapped_files={summary['unmapped_files_count']} "
            f"-> {args.out}"
        )
    else:
        sys.stdout.write(output + "\n")


if __name__ == "__main__":
    main()
