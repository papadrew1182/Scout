"""Sprint 05 Phase 4 - SQL whitelist validator for nudge rules.

Admin can register rules whose template_sql is a Postgres SELECT that
returns (member_id, entity_id, entity_kind, scheduled_for). Before
storing the rule, we parse the SQL with sqlglot (read='postgres'),
enforce a strict node + function + table whitelist, and re-serialize
the AST into canonical SQL. The scheduler executes the canonical
form only, never the raw template.

Safety bar (see docs/plans/2026-04-21-sprint-05-plan.md Section 5):

1. Parse with sqlglot.parse(template_sql, read="postgres").
2. Reject unless there is exactly one statement and the root is a
   SELECT (sqlglot exp.Select).
3. V1 allowed node types are a strict whitelist; any node outside
   the list rejects.
4. Reject any function call outside the allowlist: now, coalesce,
   lower, date_trunc, extract, count, min, max, sum,
   current_timestamp, current_date.
5. Reject any table identifier whose schema is pg_*,
   information_schema, scout, or whose table part is not in the
   approved list.
6. Reject any column reference in a disallowed schema (inherited
   from the table).
7. Reject WITH, UNION, INTERSECT, EXCEPT, any subquery, COPY, CALL,
   anonymous CTEs, PIVOT, UNNEST, window functions.
8. Reject if the raw input contains '--', '/*', or '*/'.
9. Reject multi-statement input even if semicolons are hidden
   inside strings.
10. Re-serialize the parsed AST via .sql(dialect="postgres") and
    return that canonical string. Callers store and execute the
    canonical output, never the raw template_sql.

RuleValidationError carries a bracketed tag (e.g. [disallowed-node])
so the route layer can surface stable error codes to the admin UI.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

__all__ = [
    "CanonicalSQL",
    "RuleExecutionError",
    "RuleValidationError",
    "validate_rule_sql",
]


_ALLOWED_SCHEMA = "public"

# Exact-match allowlist of tables callers may reference. Schema is
# always public. Unqualified references resolve to public via
# Postgres search_path so we tolerate both qualified and unqualified.
_ALLOWED_TABLES = frozenset(
    {
        "personal_tasks",
        "events",
        "event_attendees",
        "task_instances",
        "routines",
        "chore_templates",
        "family_members",
        "families",
        "bills",
    }
)

# Case-insensitive function allowlist. Applies to Anonymous function
# calls (unknown to sqlglot) AND to named function subclasses below.
_ALLOWED_FUNCS = frozenset(
    {
        "now",
        "coalesce",
        "lower",
        "date_trunc",
        "extract",
        "count",
        "min",
        "max",
        "sum",
        "current_timestamp",
        "current_date",
    }
)

# NOTE on named Func subclasses: sqlglot treats many AST node types
# as exp.Func subclasses that are NOT function calls in the admin's
# mental model - e.g. exp.And, exp.Or, exp.Cast. Rather than trying
# to enumerate "real functions" among Func subclasses (brittle across
# sqlglot versions), we let the strict node-name whitelist
# (_ALLOWED_NODE_NAMES below) gate named constructs. Only
# exp.Anonymous - sqlglot's catch-all for functions it does not
# recognize - is checked by name against _ALLOWED_FUNCS at walk time.
# Consequence: to add a new allowed named function (e.g. Avg,
# RowNumber), add BOTH its class name here and the lowercase
# canonical name to _ALLOWED_FUNCS.

# Strict whitelist of AST node class names that may appear in the
# walked tree. Matched against type(node).__name__ for stability
# across sqlglot minor versions. Fail-closed: anything outside this
# set triggers [disallowed-node].
_ALLOWED_NODE_NAMES: frozenset[str] = frozenset(
    {
        # Query shape
        "Select",
        "From",
        "Where",
        "Group",
        "Having",
        "Order",
        "Ordered",
        "Limit",
        "Join",
        "Paren",
        # Identifiers / references
        "Table",
        "TableAlias",
        "Column",
        "ColumnPosition",
        "Identifier",
        "Alias",
        "Star",
        # Literals
        "Literal",
        "Boolean",
        "Null",
        # Comparison / logical
        "EQ",
        "NEQ",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "And",
        "Or",
        "Not",
        "Between",
        "In",
        # Arithmetic
        "Add",
        "Sub",
        "Mul",
        "Div",
        "Neg",
        # Typing
        "Cast",
        "DataType",
        # Time
        "CurrentTimestamp",
        "CurrentDate",
        "TimeToTime",
        "Interval",
        "Var",
        # Allowed named functions
        "Coalesce",
        "Lower",
        "Count",
        "Min",
        "Max",
        "Sum",
        "Extract",
        "TimestampTrunc",
        # Anonymous is validated separately by name against _ALLOWED_FUNCS
        "Anonymous",
    }
)

# Node types that unambiguously indicate a banned construct. These
# short-circuit the walk with a descriptive error.
_BANNED_NODE_TYPES: tuple[type[exp.Expression], ...] = (
    exp.With,
    exp.CTE,
    exp.Union,
    exp.Intersect,
    exp.Except,
    exp.Subquery,
    exp.Window,
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Pivot,
    exp.Unnest,
)


class RuleValidationError(ValueError):
    """Raised when template_sql violates the Phase 4 whitelist.

    The message always starts with one of the stable bracketed tags
    documented in the module docstring (e.g. [disallowed-node]).
    """


class RuleExecutionError(RuntimeError):
    """Raised by execute_validated_rule_sql on timeout / lock / DB error.

    The message always starts with one of the stable bracketed tags:
    [timeout], [lock_timeout], [db_error], or [schema]. The scanner
    callers match on these prefixes for structured logging.
    """


@dataclass
class CanonicalSQL:
    """Validated + re-serialized SQL safe to store and execute."""

    canonical_sql: str
    referenced_tables: list[str]  # sorted, lowercased, qualified as public.TABLE


def _is_disallowed_schema(schema: str) -> bool:
    """Schemas that are categorically off-limits regardless of table."""
    if not schema:
        return False
    schema = schema.lower()
    if schema.startswith("pg_"):
        return True
    if schema in {"information_schema", "scout"}:
        return True
    return False


def _validate_table(node: exp.Table) -> str:
    """Validate a Table AST node; return qualified public.NAME on success."""
    schema = (node.db or "").lower()
    table = (node.name or "").lower()

    if _is_disallowed_schema(schema):
        raise RuleValidationError(
            f"[disallowed-schema] schema '{schema}' is not allowed"
        )

    # Any non-public schema also rejects, even if not in the categorical
    # blocklist above (defensive default-deny).
    if schema and schema != _ALLOWED_SCHEMA:
        raise RuleValidationError(
            f"[disallowed-schema] schema '{schema}' is not allowed"
        )

    # pg_* tables are often referenced unqualified (search_path
    # resolves to pg_catalog). Block those by name prefix too.
    if table.startswith("pg_"):
        raise RuleValidationError(
            f"[disallowed-table] table '{table}' is not allowed"
        )

    if table not in _ALLOWED_TABLES:
        raise RuleValidationError(
            f"[disallowed-table] table '{table}' is not allowed"
        )

    return f"{_ALLOWED_SCHEMA}.{table}"


def _validate_anonymous_function(node: exp.Anonymous) -> None:
    """Reject an Anonymous function call whose name is not in the allowlist."""
    fname = (node.name or "").lower()
    if fname not in _ALLOWED_FUNCS:
        raise RuleValidationError(
            f"[disallowed-function] function '{fname}' is not in the allowlist"
        )


def validate_rule_sql(template_sql: str) -> CanonicalSQL:
    """Parse, enforce whitelist, re-serialize.

    Raises RuleValidationError with a human-readable reason string
    prefixed by a stable bracketed tag on any violation.
    """

    if template_sql is None or not isinstance(template_sql, str):
        raise RuleValidationError("[parse] template_sql must be a non-empty string")

    # Raw text comment check - belt and suspenders beyond the AST. SQL
    # comments can carry payloads that some parsers strip silently.
    if "--" in template_sql or "/*" in template_sql or "*/" in template_sql:
        raise RuleValidationError("[comment] SQL comments are not allowed")

    try:
        parsed = sqlglot.parse(template_sql, read="postgres")
    except Exception as e:  # sqlglot.errors.ParseError and friends
        raise RuleValidationError(
            f"[parse] sqlglot could not parse: {e}"
        ) from e

    # sqlglot may emit None entries for empty trailing statements when
    # the input ends with a stray semicolon. Filter those, then count.
    parsed = [p for p in parsed if p is not None]

    if len(parsed) == 0:
        raise RuleValidationError("[parse] no statements parsed from input")

    if len(parsed) != 1:
        raise RuleValidationError(
            f"[multi-statement] exactly one statement required, got {len(parsed)}"
        )

    root = parsed[0]

    # Set-operation roots (UNION/INTERSECT/EXCEPT) are NOT Select
    # subclasses in sqlglot - they derive from SetOperation. Report
    # them as disallowed-node rather than not-select so the admin UI
    # can distinguish "you typed INSERT" from "you typed UNION".
    if isinstance(root, (exp.Union, exp.Intersect, exp.Except)):
        raise RuleValidationError(
            f"[disallowed-node] node type {type(root).__name__} is not allowed"
        )

    if not isinstance(root, exp.Select):
        raise RuleValidationError(
            f"[not-select] root must be SELECT; got {type(root).__name__}"
        )

    referenced: set[str] = set()

    for node in root.walk():
        if node is None:
            continue

        # Early short-circuit on banned node types - clearer error
        # messages than falling through to the strict whitelist below.
        if isinstance(node, _BANNED_NODE_TYPES):
            raise RuleValidationError(
                f"[disallowed-node] node type {type(node).__name__} is not allowed"
            )

        node_name = type(node).__name__

        # Strict whitelist: any node type we have not explicitly
        # vetted is rejected. Fail-closed by design. This gates both
        # "real" function nodes (Count, Coalesce, ...) and AST nodes
        # that happen to subclass exp.Func in sqlglot (And, Or, Cast).
        if node_name not in _ALLOWED_NODE_NAMES:
            raise RuleValidationError(
                f"[disallowed-node] node type {node_name} is not allowed"
            )

        # Anonymous functions (names sqlglot does not recognize) must
        # also pass the function-name allowlist. Anonymous is the ONLY
        # path by which a caller can introduce a novel function.
        if isinstance(node, exp.Anonymous):
            _validate_anonymous_function(node)

        if isinstance(node, exp.Table):
            referenced.add(_validate_table(node))

    canonical = root.sql(dialect="postgres")

    return CanonicalSQL(
        canonical_sql=canonical,
        referenced_tables=sorted(referenced),
    )
