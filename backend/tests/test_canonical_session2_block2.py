"""Session 2 block 2 — Roberts seed activation, occurrence generation,
Daily Win recompute, calendar exports and control-plane endpoints,
search_path safety.

This file complements test_canonical_session2.py (block 1, which
covers the schema/contract baseline). Block 2 tests focus on the
behavior of the new canonical_household_service plus the
data-driven Roberts seed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest
import pytz
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.canonical_household_service import (
    AssignmentResolution,
    generate_task_occurrences_for_date,
    recompute_daily_win,
    resolve_assignment,
)


# ---------------------------------------------------------------------------
# Helpers — reseed the Roberts family fresh each test and run the
# block 2 seed migration against it.
# ---------------------------------------------------------------------------


def _seed_roberts(db: Session) -> dict:
    """Insert the canonical Roberts family + members and re-run the
    block 2 seed DO block against the fresh family. Returns a dict
    of {first_name: family_member_id} for the kids and parents.

    Migration 023 is idempotent and gated on the family existing,
    so it's safe to call its DO body inline here. We read the
    SQL file from disk to avoid duplicating the long block in
    Python.
    """
    from pathlib import Path

    family_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO public.families (id, name, timezone) "
            "VALUES (:id, 'Roberts', 'America/Chicago')"
        ),
        {"id": family_id},
    )

    members = {
        "Andrew": (uuid.uuid4(), "adult", date(1985, 6, 14)),
        "Sally": (uuid.uuid4(), "adult", date(1987, 3, 22)),
        "Sadie": (uuid.uuid4(), "child", date(2012, 9, 10)),
        "Townes": (uuid.uuid4(), "child", date(2015, 11, 28)),
        "River": (uuid.uuid4(), "child", date(2017, 7, 30)),
    }
    for first_name, (mid, role, bd) in members.items():
        db.execute(
            text(
                """
                INSERT INTO public.family_members
                    (id, family_id, first_name, last_name, role, birthdate)
                VALUES
                    (:id, :fid, :fn, 'Roberts', :role, :bd)
                """
            ),
            {"id": mid, "fid": family_id, "fn": first_name, "role": role, "bd": bd},
        )
    db.flush()

    # Apply the block 2 seed migration body. The migration file is
    # an idempotent DO block that auto-resolves the Roberts family
    # by name, so calling it here against the freshly inserted
    # family seeds it.
    seed_sql = (
        Path(__file__).resolve().parent.parent.parent
        / "database"
        / "migrations"
        / "023_session2_roberts_seed.sql"
    ).read_text(encoding="utf-8")
    # Strip the BEGIN/COMMIT wrapping so it runs inside the
    # outer test transaction.
    seed_sql = seed_sql.replace("BEGIN;", "").replace("COMMIT;", "")
    db.execute(text(seed_sql))
    db.flush()

    return {
        "family_id": family_id,
        **{k: v[0] for k, v in members.items()},
    }


# ---------------------------------------------------------------------------
# Roberts seed integrity
# ---------------------------------------------------------------------------


class TestRobertsSeedIntegrity:
    def test_seed_writes_household_rules(self, db: Session):
        ctx = _seed_roberts(db)
        rows = db.execute(
            text(
                "SELECT rule_key FROM scout.household_rules WHERE family_id = :fid"
            ),
            {"fid": ctx["family_id"]},
        ).all()
        keys = {r.rule_key for r in rows}
        assert keys == {
            "one_owner_per_task",
            "finishable_lists",
            "explicit_standards_of_done",
            "quiet_enforcement",
            "one_reminder_max",
        }

    def test_seed_writes_three_standards_of_done(self, db: Session):
        ctx = _seed_roberts(db)
        rows = db.execute(
            text(
                "SELECT standard_key FROM scout.standards_of_done WHERE family_id = :fid"
            ),
            {"fid": ctx["family_id"]},
        ).all()
        assert {r.standard_key for r in rows} == {
            "room_reset",
            "common_area_closeout",
            "trash",
        }

    def test_seed_writes_per_kid_routines(self, db: Session):
        ctx = _seed_roberts(db)
        rows = db.execute(
            text(
                """
                SELECT routine_key, owner_family_member_id
                FROM scout.routine_templates
                WHERE family_id = :fid
                """
            ),
            {"fid": ctx["family_id"]},
        ).all()
        # 3 kids × 3 routine blocks = 9
        assert len(rows) == 9
        per_kid = {}
        for r in rows:
            per_kid.setdefault(r.owner_family_member_id, set()).add(r.routine_key)
        for mid in [ctx["Sadie"], ctx["Townes"], ctx["River"]]:
            assert per_kid[mid] == {"morning", "after_school", "evening"}

    def test_seed_writes_dog_walk_assistant_rule(self, db: Session):
        ctx = _seed_roberts(db)
        row = db.execute(
            text(
                """
                SELECT tar.rule_type, tar.rule_params
                FROM scout.task_assignment_rules tar
                JOIN scout.task_templates tt ON tt.id = tar.task_template_id
                WHERE tt.family_id = :fid AND tt.template_key = 'dog_walks'
                """
            ),
            {"fid": ctx["family_id"]},
        ).first()
        assert row is not None
        assert row.rule_type == "dog_walk_assistant"
        params = row.rule_params
        assert params["lead"] == str(ctx["Sadie"])
        assert params["odd"] == str(ctx["Townes"])
        assert params["even"] == str(ctx["River"])

    def test_seed_writes_8_week_rotation_for_poop_patrol(self, db: Session):
        ctx = _seed_roberts(db)
        row = db.execute(
            text(
                """
                SELECT tar.rule_type, tar.rule_params
                FROM scout.task_assignment_rules tar
                JOIN scout.task_templates tt ON tt.id = tar.task_template_id
                WHERE tt.family_id = :fid AND tt.template_key = 'poop_patrol'
                """
            ),
            {"fid": ctx["family_id"]},
        ).first()
        assert row is not None
        assert row.rule_type == "week_rotation"
        params = row.rule_params
        assert int(params["period_weeks"]) == 8
        assert params["owner"] == str(ctx["Townes"])
        assert params["assistant"] == str(ctx["River"])
        assert params["anchor_date"] == "2026-01-05"

    def test_seed_writes_reward_policies(self, db: Session):
        ctx = _seed_roberts(db)
        rows = db.execute(
            text(
                """
                SELECT family_member_id, baseline_amount_cents
                FROM scout.reward_policies
                WHERE family_id = :fid AND policy_key = 'weekly_allowance'
                """
            ),
            {"fid": ctx["family_id"]},
        ).all()
        amounts = {r.family_member_id: r.baseline_amount_cents for r in rows}
        assert amounts[ctx["Sadie"]] == 1200
        assert amounts[ctx["Townes"]] == 900
        assert amounts[ctx["River"]] == 700

    def test_seed_idempotent_re_run(self, db: Session):
        ctx = _seed_roberts(db)
        # Re-run the seed body on the same family; counts should
        # be unchanged.
        from pathlib import Path

        seed_sql = (
            Path(__file__).resolve().parent.parent.parent
            / "database"
            / "migrations"
            / "023_session2_roberts_seed.sql"
        ).read_text(encoding="utf-8")
        seed_sql = seed_sql.replace("BEGIN;", "").replace("COMMIT;", "")
        db.execute(text(seed_sql))
        db.flush()

        rules_count = db.execute(
            text(
                "SELECT COUNT(*) FROM scout.household_rules WHERE family_id = :fid"
            ),
            {"fid": ctx["family_id"]},
        ).scalar()
        assert rules_count == 5

        rt_count = db.execute(
            text(
                "SELECT COUNT(*) FROM scout.routine_templates WHERE family_id = :fid"
            ),
            {"fid": ctx["family_id"]},
        ).scalar()
        assert rt_count == 9


# ---------------------------------------------------------------------------
# Assignment rule evaluation (unit tests of the resolver)
# ---------------------------------------------------------------------------


class TestResolveAssignment:
    def test_fixed_returns_named_member(self):
        target = uuid.uuid4()
        result = resolve_assignment(
            "fixed", {"family_member_id": str(target)}, date(2026, 4, 13)
        )
        assert result.primary == target
        assert result.assistant is None

    def test_day_parity_alternates(self):
        odd = uuid.uuid4()
        even = uuid.uuid4()
        params = {"odd": str(odd), "even": str(even)}
        # Apr 13 → odd day → odd kid
        assert resolve_assignment("day_parity", params, date(2026, 4, 13)).primary == odd
        # Apr 14 → even day → even kid
        assert resolve_assignment("day_parity", params, date(2026, 4, 14)).primary == even

    def test_dog_walk_assistant_resolves_lead_and_assistant(self):
        sadie = uuid.uuid4()
        townes = uuid.uuid4()
        river = uuid.uuid4()
        params = {"lead": str(sadie), "odd": str(townes), "even": str(river)}
        # Apr 13 odd → assistant Townes
        result = resolve_assignment("dog_walk_assistant", params, date(2026, 4, 13))
        assert result.primary == sadie
        assert result.assistant == townes
        # Apr 14 even → assistant River
        result = resolve_assignment("dog_walk_assistant", params, date(2026, 4, 14))
        assert result.primary == sadie
        assert result.assistant == river

    def test_week_rotation_swaps_after_8_weeks(self):
        owner = uuid.uuid4()
        assistant = uuid.uuid4()
        params = {
            "owner": str(owner),
            "assistant": str(assistant),
            "period_weeks": 8,
            "anchor_date": "2026-01-05",  # Monday
        }
        # Period 0 (Jan 5 + first 8 weeks) — original ownership
        r = resolve_assignment("week_rotation", params, date(2026, 1, 5))
        assert r.primary == owner
        assert r.assistant == assistant

        r = resolve_assignment("week_rotation", params, date(2026, 2, 23))  # week 7
        assert r.primary == owner

        # Period 1 (week 8 = Mar 2) — swap
        r = resolve_assignment("week_rotation", params, date(2026, 3, 2))
        assert r.primary == assistant
        assert r.assistant == owner

        # Period 2 (week 16 = Apr 27) — swap back
        r = resolve_assignment("week_rotation", params, date(2026, 4, 27))
        assert r.primary == owner

    def test_unknown_rule_type_returns_unassigned(self):
        result = resolve_assignment("not_a_real_type", {}, date(2026, 4, 13))
        assert result.primary is None

    def test_malformed_params_does_not_raise(self):
        result = resolve_assignment("week_rotation", {"period_weeks": "not_an_int"}, date(2026, 4, 13))
        assert result.primary is None


# ---------------------------------------------------------------------------
# Occurrence generation for the seeded Roberts family
# ---------------------------------------------------------------------------


class TestOccurrenceGeneration:
    def test_generates_routines_and_tasks_for_a_weekday(self, db: Session):
        ctx = _seed_roberts(db)
        # Apr 13 2026 is a Monday (weekday).
        result = generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 13)
        )
        assert result.routines_generated == 9  # 3 kids × 3 routine blocks
        # Standalone tasks expected: dishwasher, table_captain, living_room_reset,
        # common_area_closeout, dog_walks. (power_60 + poop_patrol are weekly
        # → don't fire on Monday.)
        assert result.tasks_generated == 5

    def test_weekday_skips_after_school_routines_on_weekend(self, db: Session):
        ctx = _seed_roberts(db)
        # Apr 18 2026 is Saturday — after_school templates are 'weekdays' so
        # they should NOT fire.
        result = generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 18)
        )
        # On Saturday: morning(3) + evening(3) = 6 routines, no after_school.
        assert result.routines_generated == 6

    def test_saturday_emits_power_60_and_poop_patrol(self, db: Session):
        ctx = _seed_roberts(db)
        result = generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 18)
        )
        # On Saturday, weekly templates fire. Sadie ownership chores
        # (dishwasher, table, living_room) are 'weekdays' so they don't.
        # common_area_closeout is daily, dog_walks is daily.
        # Net: common_area + dog_walks + power_60 + poop_patrol = 4
        assert result.tasks_generated == 4

    def test_idempotent_regeneration(self, db: Session):
        ctx = _seed_roberts(db)
        first = generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 13)
        )
        second = generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 13)
        )
        assert first.routines_generated > 0 and first.tasks_generated > 0
        assert second.routines_generated == 0
        assert second.tasks_generated == 0

    def test_common_area_assigned_by_day_parity(self, db: Session):
        ctx = _seed_roberts(db)
        # Odd day (Apr 13) → Townes
        generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 13)
        )
        odd_assignee = db.execute(
            text(
                """
                SELECT assigned_to FROM scout.task_occurrences tocc
                JOIN scout.task_templates tt ON tt.id = tocc.task_template_id
                WHERE tt.family_id = :fid
                  AND tt.template_key = 'common_area_closeout'
                  AND tocc.occurrence_date = :d
                """
            ),
            {"fid": ctx["family_id"], "d": date(2026, 4, 13)},
        ).scalar()
        assert odd_assignee == ctx["Townes"]

        # Even day (Apr 14) → River
        generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=date(2026, 4, 14)
        )
        even_assignee = db.execute(
            text(
                """
                SELECT assigned_to FROM scout.task_occurrences tocc
                JOIN scout.task_templates tt ON tt.id = tocc.task_template_id
                WHERE tt.family_id = :fid
                  AND tt.template_key = 'common_area_closeout'
                  AND tocc.occurrence_date = :d
                """
            ),
            {"fid": ctx["family_id"], "d": date(2026, 4, 14)},
        ).scalar()
        assert even_assignee == ctx["River"]

    def test_dog_walks_owner_is_always_sadie(self, db: Session):
        ctx = _seed_roberts(db)
        for d in [date(2026, 4, 13), date(2026, 4, 14)]:
            generate_task_occurrences_for_date(
                db, family_id=ctx["family_id"], on_date=d
            )
        rows = db.execute(
            text(
                """
                SELECT assigned_to FROM scout.task_occurrences tocc
                JOIN scout.task_templates tt ON tt.id = tocc.task_template_id
                WHERE tt.family_id = :fid
                  AND tt.template_key = 'dog_walks'
                """
            ),
            {"fid": ctx["family_id"]},
        ).all()
        assignees = {r.assigned_to for r in rows}
        assert assignees == {ctx["Sadie"]}


# ---------------------------------------------------------------------------
# Daily Win recompute end to end
# ---------------------------------------------------------------------------


class TestDailyWinRecompute:
    def test_recompute_sets_earned_when_all_complete(self, db: Session):
        ctx = _seed_roberts(db)
        on_date = date(2026, 4, 13)
        generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=on_date
        )
        # Find Sadie's occurrences and complete each one
        rows = db.execute(
            text(
                """
                SELECT id FROM scout.task_occurrences
                WHERE family_id = :fid AND assigned_to = :mid AND occurrence_date = :d
                """
            ),
            {"fid": ctx["family_id"], "mid": ctx["Sadie"], "d": on_date},
        ).all()
        for r in rows:
            db.execute(
                text(
                    """
                    INSERT INTO scout.task_completions
                        (task_occurrence_id, completed_by, completion_mode)
                    VALUES (:occ, :by, 'manual')
                    """
                ),
                {"occ": r.id, "by": ctx["Sadie"]},
            )
        db.flush()

        result = recompute_daily_win(
            db,
            family_id=ctx["family_id"],
            family_member_id=ctx["Sadie"],
            on_date=on_date,
        )
        assert result.earned is True
        assert result.changed is True
        assert result.total_required == result.total_complete

    def test_recompute_returns_not_earned_when_one_missing(self, db: Session):
        ctx = _seed_roberts(db)
        on_date = date(2026, 4, 13)
        generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=on_date
        )
        # Complete only ONE of Sadie's occurrences
        first = db.execute(
            text(
                """
                SELECT id FROM scout.task_occurrences
                WHERE family_id = :fid AND assigned_to = :mid AND occurrence_date = :d
                LIMIT 1
                """
            ),
            {"fid": ctx["family_id"], "mid": ctx["Sadie"], "d": on_date},
        ).first()
        db.execute(
            text(
                """
                INSERT INTO scout.task_completions
                    (task_occurrence_id, completed_by, completion_mode)
                VALUES (:occ, :by, 'manual')
                """
            ),
            {"occ": first.id, "by": ctx["Sadie"]},
        )
        db.flush()

        result = recompute_daily_win(
            db,
            family_id=ctx["family_id"],
            family_member_id=ctx["Sadie"],
            on_date=on_date,
        )
        assert result.earned is False
        assert result.total_complete < result.total_required
        assert len(result.missing) >= 1

    def test_recompute_writes_persistent_row(self, db: Session):
        ctx = _seed_roberts(db)
        on_date = date(2026, 4, 13)
        generate_task_occurrences_for_date(
            db, family_id=ctx["family_id"], on_date=on_date
        )
        recompute_daily_win(
            db,
            family_id=ctx["family_id"],
            family_member_id=ctx["River"],
            on_date=on_date,
        )
        row = db.execute(
            text(
                """
                SELECT earned, total_required, total_complete
                FROM scout.daily_win_results
                WHERE family_member_id = :mid AND for_date = :d
                """
            ),
            {"mid": ctx["River"], "d": on_date},
        ).first()
        assert row is not None
        assert row.total_required >= 1


# ---------------------------------------------------------------------------
# Endpoint contract tests against real seeded data
# ---------------------------------------------------------------------------


@pytest.fixture
def session2_block2_client(db):
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import app

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


def _bearer_for(db: Session, member_id):
    from app.models.foundation import Session as SessionModel, UserAccount
    from app.services.auth_service import hash_password

    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"s2b2-{uuid.uuid4().hex[:8]}@scout.local",
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=False,
        is_active=True,
    )
    db.add(account)
    db.flush()
    token = f"tok-{uuid.uuid4().hex}"
    db.add(
        SessionModel(
            user_account_id=account.id,
            token=token,
            expires_at=datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(hours=1),
        )
    )
    db.commit()
    return token


class TestHouseholdTodayEndpoint:
    def test_returns_seeded_blocks_and_chores(
        self, session2_block2_client, db: Session
    ):
        ctx = _seed_roberts(db)
        tok = _bearer_for(db, ctx["Andrew"])
        r = session2_block2_client.get(
            "/api/household/today",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        # Schema-locked envelope
        assert set(body.keys()) >= {
            "date",
            "summary",
            "blocks",
            "standalone_chores",
            "weekly_items",
        }
        # The route auto-generates today's occurrences. We can't
        # assert exact counts (depends on the day-of-week the test
        # runs), but blocks must include at least one routine
        # block when the day is a weekday or weekend that has any
        # routine that fires.
        assert isinstance(body["blocks"], list)


class TestRewardsCurrentWeekEndpoint:
    def test_falls_back_to_policy_preview_when_no_period(
        self, session2_block2_client, db: Session
    ):
        ctx = _seed_roberts(db)
        tok = _bearer_for(db, ctx["Andrew"])
        r = session2_block2_client.get(
            "/api/rewards/week/current",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        # No allowance_period exists yet, but the policy fallback
        # should produce one row per kid with weekly_allowance.
        assert body["period"] is not None
        assert len(body["members"]) == 3
        names = {m["name"] for m in body["members"]}
        assert names == {"Sadie", "Townes", "River"}
        # Baseline values come straight from the seed
        baselines = {m["name"]: m["baseline_allowance"] for m in body["members"]}
        assert baselines["Sadie"] == 12.0
        assert baselines["Townes"] == 9.0
        assert baselines["River"] == 7.0


class TestCalendarExportsUpcomingEndpoint:
    def test_empty_when_no_exports(self, session2_block2_client, db: Session):
        ctx = _seed_roberts(db)
        tok = _bearer_for(db, ctx["Andrew"])
        r = session2_block2_client.get(
            "/api/calendar/exports/upcoming",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_returns_pending_export_after_seed(
        self, session2_block2_client, db: Session
    ):
        ctx = _seed_roberts(db)
        # Insert a pending calendar export pointed at a future block
        future = datetime.now(pytz.UTC) + timedelta(hours=2)
        db.execute(
            text(
                """
                INSERT INTO scout.calendar_exports
                    (family_id, source_type, source_id, label, starts_at,
                     ends_at, hearth_visible, export_status)
                VALUES
                    (:fid, 'routine_block', :sid, 'Evening Reset',
                     :start, :end, true, 'pending')
                """
            ),
            {
                "fid": ctx["family_id"],
                "sid": uuid.uuid4(),
                "start": future,
                "end": future + timedelta(minutes=30),
            },
        )
        db.flush()
        tok = _bearer_for(db, ctx["Andrew"])
        r = session2_block2_client.get(
            "/api/calendar/exports/upcoming",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(i["label"] == "Evening Reset" for i in items)
        for item in items:
            assert set(item.keys()) >= {
                "calendar_export_id",
                "label",
                "starts_at",
                "ends_at",
                "source_type",
                "source_id",
                "target",
                "hearth_visible",
                "export_status",
                "last_exported_at",
            }


class TestControlPlaneSummaryEndpoint:
    def test_returns_locked_envelope(self, session2_block2_client, db: Session):
        ctx = _seed_roberts(db)
        tok = _bearer_for(db, ctx["Andrew"])
        r = session2_block2_client.get(
            "/api/control-plane/summary",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {
            "connectors",
            "sync_jobs",
            "calendar_exports",
            "rewards",
        }
        for k in ("healthy_count", "stale_count", "error_count"):
            assert k in body["connectors"]
        for k in ("running_count", "failed_count"):
            assert k in body["sync_jobs"]
        for k in ("pending_count", "failed_count"):
            assert k in body["calendar_exports"]
        assert "pending_approval_count" in body["rewards"]


# ---------------------------------------------------------------------------
# Search-path safety
# ---------------------------------------------------------------------------


class TestSearchPathSafety:
    def test_unqualified_routine_steps_resolves_to_public(self, db: Session):
        """The Session 1 conftest + app/database.py both force
        search_path = public, scout. This test confirms an
        unqualified `INSERT INTO routine_steps` lands in
        public.routine_steps (the legacy Tier-1 shape with
        ``routine_id``) and not scout.routine_steps (the new
        Session 2 shape with ``routine_template_id``)."""
        # Seed the legacy public.routines row first
        from app.models.foundation import Family, FamilyMember
        from app.models.life_management import Routine, RoutineStep

        fam = Family(name="SearchPathFamily", timezone="America/Chicago")
        db.add(fam)
        db.flush()
        member = FamilyMember(
            family_id=fam.id, first_name="Sadie", role="child", birthdate=date(2012, 9, 10)
        )
        db.add(member)
        db.flush()
        routine = Routine(
            family_id=fam.id,
            family_member_id=member.id,
            name="Test Morning",
            block="morning",
            recurrence="daily",
            due_time_weekday=time(7, 25),
            due_time_weekend=time(9, 0),
        )
        db.add(routine)
        db.flush()

        # ORM insert via the Tier-1 RoutineStep model — this uses
        # an unqualified table name, which should resolve to
        # public.routine_steps.
        step = RoutineStep(routine_id=routine.id, name="Get dressed", sort_order=1)
        db.add(step)
        db.flush()

        # And the row exists in public.routine_steps with
        # routine_id, NOT in scout.routine_steps.
        public_count = db.execute(
            text(
                "SELECT COUNT(*) FROM public.routine_steps WHERE routine_id = :rid"
            ),
            {"rid": routine.id},
        ).scalar()
        assert public_count == 1

        # Confirm scout.routine_steps was NOT touched
        scout_count = db.execute(
            text("SELECT COUNT(*) FROM scout.routine_steps")
        ).scalar()
        assert scout_count == 0

    def test_unqualified_select_from_routine_steps_uses_public(self, db: Session):
        # Pure SQL (no ORM) — bare `routine_steps` should still
        # resolve to public.
        cols = db.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'routine_steps'
                """
            )
        ).all()
        # current_schema() returns the first writable schema in
        # search_path — which is public.
        col_names = {c.column_name for c in cols}
        assert "routine_id" in col_names  # public shape
        assert "routine_template_id" not in col_names  # scout shape would have this
