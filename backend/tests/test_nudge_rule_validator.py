"""Attack suite for nudge_rule_validator (Sprint 05 Phase 4 Task 3).

Per revised plan Section 5, this validator is the v1 defense-in-depth
for admin-configurable nudge rule SQL. It MUST land with its attack
suite BEFORE any CRUD route is wired. The tests below exercise the
safety bar documented in app/services/nudge_rule_validator.py.

Structure:
- Rejection cases: input -> expected bracketed tag (e.g. [disallowed-node]).
- Acceptance cases: input must round-trip to canonical SQL, list the
  referenced tables in qualified form, and be idempotent.
"""

from __future__ import annotations

import pytest

from app.services.nudge_rule_validator import (
    CanonicalSQL,
    RuleValidationError,
    validate_rule_sql,
)


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql,allowed_tags",
    [
        # 1. DROP TABLE - not a select; sqlglot parses as Drop
        pytest.param(
            "DROP TABLE personal_tasks",
            ("[not-select]", "[disallowed-node]"),
            id="drop_table",
        ),
        # 2. INSERT
        pytest.param(
            "INSERT INTO personal_tasks (title) VALUES ('x')",
            ("[not-select]",),
            id="insert",
        ),
        # 3. UPDATE
        pytest.param(
            "UPDATE personal_tasks SET status = 'done'",
            ("[not-select]",),
            id="update",
        ),
        # 4. DELETE
        pytest.param(
            "DELETE FROM personal_tasks",
            ("[not-select]",),
            id="delete",
        ),
        # 5. TRUNCATE
        pytest.param(
            "TRUNCATE personal_tasks",
            ("[not-select]", "[disallowed-node]"),
            id="truncate",
        ),
        # 6. GRANT
        pytest.param(
            "GRANT SELECT ON personal_tasks TO scout_rule_reader",
            ("[not-select]", "[disallowed-node]"),
            id="grant",
        ),
        # 7. CREATE TABLE
        pytest.param(
            "CREATE TABLE x (id uuid)",
            ("[not-select]", "[disallowed-node]"),
            id="create_table",
        ),
        # 8. ALTER TABLE
        pytest.param(
            "ALTER TABLE personal_tasks DROP COLUMN id",
            ("[not-select]", "[disallowed-node]"),
            id="alter_table",
        ),
        # 9. Multi-statement
        pytest.param(
            "SELECT id FROM personal_tasks; DROP TABLE personal_tasks",
            ("[multi-statement]",),
            id="multi_statement",
        ),
        # 10. WITH
        pytest.param(
            "WITH x AS (SELECT 1) SELECT * FROM x",
            ("[disallowed-node]",),
            id="with_cte",
        ),
        # 11. UNION
        pytest.param(
            "SELECT 1 UNION SELECT 2",
            ("[disallowed-node]",),
            id="union",
        ),
        # 12. INTERSECT
        pytest.param(
            "SELECT 1 INTERSECT SELECT 2",
            ("[disallowed-node]",),
            id="intersect",
        ),
        # 13. EXCEPT
        pytest.param(
            "SELECT 1 EXCEPT SELECT 2",
            ("[disallowed-node]",),
            id="except",
        ),
        # 14. Subquery
        pytest.param(
            "SELECT id FROM personal_tasks WHERE id IN (SELECT id FROM events)",
            ("[disallowed-node]",),
            id="subquery_in_where",
        ),
        # 15. COPY
        pytest.param(
            "COPY personal_tasks TO '/tmp/x.csv'",
            ("[not-select]", "[disallowed-node]"),
            id="copy",
        ),
        # 16. CALL
        pytest.param(
            "CALL some_proc()",
            ("[not-select]",),
            id="call",
        ),
        # 17. pg_sleep - parses as SELECT pg_sleep(10) with Anonymous
        pytest.param(
            "SELECT pg_sleep(10)",
            ("[disallowed-function]",),
            id="pg_sleep",
        ),
        # 18. pg_* unqualified table
        pytest.param(
            "SELECT * FROM pg_stat_activity",
            ("[disallowed-table]", "[disallowed-schema]"),
            id="pg_stat_activity",
        ),
        # 19. information_schema
        pytest.param(
            "SELECT table_name FROM information_schema.tables",
            ("[disallowed-schema]",),
            id="information_schema",
        ),
        # 20. scout schema
        pytest.param(
            "SELECT * FROM scout.permissions",
            ("[disallowed-schema]",),
            id="scout_schema",
        ),
        # 21. Table not in allowlist
        pytest.param(
            "SELECT * FROM ai_messages",
            ("[disallowed-table]",),
            id="ai_messages_not_allowed",
        ),
        # 22. Line comment
        pytest.param(
            "SELECT id FROM personal_tasks -- DROP TABLE personal_tasks",
            ("[comment]",),
            id="line_comment",
        ),
        # 23. Block comment
        pytest.param(
            "SELECT id FROM personal_tasks /* bad */",
            ("[comment]",),
            id="block_comment",
        ),
        # 25. Window function (row_number OVER ...)
        pytest.param(
            "SELECT row_number() OVER (ORDER BY id) FROM personal_tasks",
            ("[disallowed-node]", "[disallowed-function]"),
            id="window_function",
        ),
    ],
)
def test_rejection_cases(sql: str, allowed_tags: tuple[str, ...]) -> None:
    """Each input must raise RuleValidationError with one of the allowed tags."""
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_sql(sql)
    msg = str(exc.value)
    assert any(
        msg.startswith(tag) for tag in allowed_tags
    ), f"expected one of {allowed_tags}, got: {msg!r}"


# Case 24 is a lock-in test rather than a parametrized rejection: we
# commit to ACCEPTING embedded semicolons inside string literals and
# relying on the AST for multi-statement detection. If you ever want
# to flip this to reject, change the assertion below and update the
# docstring in nudge_rule_validator.
def test_case_24_embedded_semicolon_in_literal_is_accepted() -> None:
    """Semicolons inside string literals must not trip the validator.

    The AST parse gives us exactly one Select statement; that is the
    authoritative signal, not a naive string scan.
    """
    result = validate_rule_sql(
        "SELECT id FROM personal_tasks WHERE title = 'a;b'"
    )
    assert isinstance(result, CanonicalSQL)
    assert "'a;b'" in result.canonical_sql
    assert result.referenced_tables == ["public.personal_tasks"]


# ---------------------------------------------------------------------------
# Acceptance cases
# ---------------------------------------------------------------------------


ACCEPTANCE_CASES: list[tuple[str, str, list[str]]] = [
    # id, input_sql, expected_referenced_tables (sorted qualified)
    (
        "overdue_personal_tasks",
        "SELECT assigned_to, id, 'personal_task' AS kind, due_at "
        "FROM personal_tasks WHERE status = 'overdue' LIMIT 100",
        ["public.personal_tasks"],
    ),
    (
        "events_with_attendees",
        "SELECT e.id, e.starts_at FROM events e "
        "JOIN event_attendees a ON a.event_id = e.id "
        "WHERE e.starts_at > now() LIMIT 50",
        ["public.event_attendees", "public.events"],
    ),
    (
        "task_instances_overdue",
        "SELECT id, due_at FROM task_instances "
        "WHERE is_completed = false AND due_at < now()",
        ["public.task_instances"],
    ),
    (
        "count_pending",
        "SELECT COUNT(*) FROM personal_tasks WHERE status = 'pending'",
        ["public.personal_tasks"],
    ),
    (
        "order_by_limit",
        "SELECT id FROM personal_tasks ORDER BY due_at DESC LIMIT 10",
        ["public.personal_tasks"],
    ),
]


@pytest.mark.parametrize(
    "case_id,sql,expected_tables",
    [(c[0], c[1], c[2]) for c in ACCEPTANCE_CASES],
    ids=[c[0] for c in ACCEPTANCE_CASES],
)
def test_acceptance_cases(
    case_id: str, sql: str, expected_tables: list[str]
) -> None:
    result = validate_rule_sql(sql)

    assert isinstance(result, CanonicalSQL)
    assert result.canonical_sql.lower().startswith("select")
    assert result.referenced_tables == expected_tables


@pytest.mark.parametrize(
    "case_id,sql,expected_tables",
    [(c[0], c[1], c[2]) for c in ACCEPTANCE_CASES],
    ids=[c[0] for c in ACCEPTANCE_CASES],
)
def test_canonical_sql_is_idempotent(
    case_id: str, sql: str, expected_tables: list[str]
) -> None:
    """Feeding canonical output back into validate must be stable."""
    once = validate_rule_sql(sql)
    twice = validate_rule_sql(once.canonical_sql)
    assert once.canonical_sql == twice.canonical_sql
    assert once.referenced_tables == twice.referenced_tables


# ---------------------------------------------------------------------------
# Additional defensive cases
# ---------------------------------------------------------------------------


def test_public_qualified_table_is_accepted() -> None:
    """public.personal_tasks must be treated as equivalent to the unqualified form."""
    result = validate_rule_sql("SELECT id FROM public.personal_tasks LIMIT 5")
    assert result.referenced_tables == ["public.personal_tasks"]


def test_pg_catalog_qualified_table_is_rejected() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_sql("SELECT * FROM pg_catalog.pg_tables")
    assert str(exc.value).startswith("[disallowed-schema]")


def test_empty_string_rejected_cleanly() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_sql("")
    # Empty input can present as either parse failure or zero
    # statements; both start with [parse].
    assert str(exc.value).startswith("[parse]")


def test_trailing_semicolon_accepted_as_single_statement() -> None:
    """One statement followed by whitespace/empty is still one statement."""
    result = validate_rule_sql(
        "SELECT id FROM personal_tasks WHERE status = 'pending';"
    )
    assert result.canonical_sql.lower().startswith("select")
    assert result.referenced_tables == ["public.personal_tasks"]


def test_upper_case_function_still_validated() -> None:
    """Function allowlist must be case-insensitive for Anonymous calls."""
    # NOW() and COUNT() still round-trip fine; they are handled by
    # named Func subclasses (CurrentTimestamp, Count) not Anonymous.
    result = validate_rule_sql(
        "SELECT COUNT(*) FROM personal_tasks WHERE due_at < NOW()"
    )
    assert result.canonical_sql.lower().startswith("select")
