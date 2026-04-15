"""Shared fixtures: test database, session, and seeded family data.

Uses a real PostgreSQL database (scout_test). Schema is built by running
the actual SQL migrations (not ORM create_all) so CHECK constraints,
unique indexes, and triggers match production.

Each test runs in a transaction that is rolled back after the test completes.
"""

import uuid
from collections.abc import Generator
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.foundation import Family, FamilyMember
from app.models.life_management import ChoreTemplate, Routine, RoutineStep

TEST_DATABASE_URL = "postgresql://scout:scout@localhost:5432/scout_test"
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "database" / "migrations"

engine = create_engine(TEST_DATABASE_URL)

# Mirror app.database's search_path guard. Postgres default
# search_path resolves "$user" to the DB role name ("scout"), which
# after migration 022 creates the scout schema shadows unqualified
# references to public tables that still hold the legacy shape.
# Force public,scout so legacy unqualified queries hit public first.
from sqlalchemy import event as _event  # noqa: E402


@_event.listens_for(engine, "connect")
def _set_test_search_path(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SET search_path TO public, scout")
    finally:
        cursor.close()


TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Session 2 added the `scout` and `connector_*` schemas. The test
# harness must drop THEM too — otherwise cross-schema views from
# scout.* hanging on to public.* rows survive pytest session
# boundaries and fail the next migration run.
_MANAGED_SCHEMAS = [
    "scout",
    "connector_google_calendar",
    "connector_greenlight",
    "connector_rex",
    "connector_ynab",
    "connector_apple_health",
    "connector_nike_run_club",
    "connector_exxir",
]


def _reset_managed_schemas(conn) -> None:
    """Drop public + every Session-2 schema and recreate public.
    Idempotent and safe on the first run (DROP ... IF EXISTS CASCADE).
    """
    for schema in _MANAGED_SCHEMAS:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    conn.execute(text("DROP SCHEMA public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO scout"))


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Build test schema from real SQL migrations."""
    with engine.connect() as conn:
        _reset_managed_schemas(conn)
        conn.commit()

        # Run each migration in order
        for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = migration_file.read_text(encoding="utf-8")
            conn.execute(text(sql))
            conn.commit()

    yield

    # Teardown: drop public + all session-2 managed schemas.
    with engine.connect() as conn:
        _reset_managed_schemas(conn)
        conn.commit()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Provide a transactional session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Seeded family data
# ---------------------------------------------------------------------------

@pytest.fixture()
def family(db: Session) -> Family:
    f = Family(name="Roberts", timezone="America/Chicago")
    db.add(f)
    db.flush()
    return f


@pytest.fixture()
def adults(db: Session, family: Family) -> dict[str, FamilyMember]:
    robert = FamilyMember(family_id=family.id, first_name="Robert", last_name="Roberts", role="adult", birthdate=date(1985, 6, 14))
    megan = FamilyMember(family_id=family.id, first_name="Megan", last_name="Roberts", role="adult", birthdate=date(1987, 3, 22))
    db.add_all([robert, megan])
    db.flush()
    return {"robert": robert, "megan": megan}


@pytest.fixture()
def children(db: Session, family: Family) -> dict[str, FamilyMember]:
    sadie = FamilyMember(family_id=family.id, first_name="Sadie", role="child", birthdate=date(2012, 9, 10))
    townes = FamilyMember(family_id=family.id, first_name="Townes", role="child", birthdate=date(2015, 11, 28))
    river = FamilyMember(family_id=family.id, first_name="River", role="child", birthdate=date(2017, 7, 4))
    db.add_all([sadie, townes, river])
    db.flush()
    return {"sadie": sadie, "townes": townes, "river": river}


@pytest.fixture()
def sadie_routines(db: Session, family: Family, children: dict) -> list[Routine]:
    sadie = children["sadie"]
    routines = [
        Routine(family_id=family.id, family_member_id=sadie.id, name="Sadie Morning", block="morning", recurrence="daily", due_time_weekday=time(7, 25), due_time_weekend=time(9, 0)),
        Routine(family_id=family.id, family_member_id=sadie.id, name="Sadie After School", block="after_school", recurrence="weekdays", due_time_weekday=time(17, 30)),
        Routine(family_id=family.id, family_member_id=sadie.id, name="Sadie Evening", block="evening", recurrence="daily", due_time_weekday=time(21, 30), due_time_weekend=time(21, 30)),
    ]
    db.add_all(routines)
    db.flush()

    morning = routines[0]
    steps = [
        RoutineStep(routine_id=morning.id, name="Get dressed", sort_order=1),
        RoutineStep(routine_id=morning.id, name="Make bed", sort_order=2),
        RoutineStep(routine_id=morning.id, name="Brush teeth", sort_order=3),
    ]
    db.add_all(steps)
    db.flush()
    return routines


@pytest.fixture()
def dog_walk_templates(db: Session, family: Family, children: dict) -> dict[str, ChoreTemplate]:
    sadie = children["sadie"]
    townes = children["townes"]
    river = children["river"]

    lead = ChoreTemplate(
        family_id=family.id, name="Dog Walks (Sadie lead)", recurrence="daily",
        due_time=time(19, 30), assignment_type="fixed",
        assignment_rule={"assigned_to": str(sadie.id)},
    )
    assistant = ChoreTemplate(
        family_id=family.id, name="Dog Walk Assistant (Willie)", recurrence="daily",
        due_time=time(19, 30), assignment_type="rotating_daily",
        assignment_rule={"rule": "day_parity", "odd": str(townes.id), "even": str(river.id)},
    )
    db.add_all([lead, assistant])
    db.flush()
    return {"lead": lead, "assistant": assistant}


@pytest.fixture()
def dishwasher_template(db: Session, family: Family, children: dict) -> ChoreTemplate:
    sadie = children["sadie"]
    t = ChoreTemplate(
        family_id=family.id, name="Dishwasher Captain", recurrence="weekdays",
        due_time=time(20, 0), assignment_type="fixed",
        assignment_rule={"assigned_to": str(sadie.id)},
    )
    db.add(t)
    db.flush()
    return t
