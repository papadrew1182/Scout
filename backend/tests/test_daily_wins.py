"""Tests for daily_win_service.

Covers:
- all tasks complete → win
- one missed task → no win
- parent override makes incomplete task count as win
- weekend dates are skipped
"""

from datetime import date, datetime, time

import pytz
from sqlalchemy.orm import Session

from app.models.life_management import Routine, TaskInstance
from app.services.daily_win_service import compute_daily_win, compute_for_family_date


def _make_instance(
    db: Session,
    family_id,
    member_id,
    routine_id,
    instance_date: date,
    due_hour: int,
    completed: bool,
    completed_before_deadline: bool = True,
    override_completed: bool | None = None,
    override_by=None,
) -> TaskInstance:
    tz = pytz.timezone("America/Chicago")
    due_at = tz.localize(datetime.combine(instance_date, time(due_hour, 0)))
    completed_at = None
    if completed:
        offset = -1 if completed_before_deadline else 1
        completed_at = tz.localize(datetime.combine(instance_date, time(due_hour + offset, 0)))

    ti = TaskInstance(
        family_id=family_id,
        family_member_id=member_id,
        routine_id=routine_id,
        chore_template_id=None,
        instance_date=instance_date,
        due_at=due_at,
        is_completed=completed,
        completed_at=completed_at,
        override_completed=override_completed,
        override_by=override_by,
    )
    db.add(ti)
    db.flush()
    return ti


class TestAllComplete:
    def test_all_completed_by_deadline_is_win(self, db: Session, family, children, sadie_routines):
        sadie = children["sadie"]
        target = date(2026, 3, 30)  # Monday

        for routine in sadie_routines:
            _make_instance(db, family.id, sadie.id, routine.id, target, due_hour=20, completed=True)

        win = compute_daily_win(db, family.id, sadie.id, target)

        assert win.is_win is True
        assert win.task_count == 3
        assert win.completed_count == 3


class TestMissedTask:
    def test_one_incomplete_is_not_win(self, db: Session, family, children, sadie_routines):
        sadie = children["sadie"]
        target = date(2026, 3, 30)

        _make_instance(db, family.id, sadie.id, sadie_routines[0].id, target, due_hour=8, completed=True)
        _make_instance(db, family.id, sadie.id, sadie_routines[1].id, target, due_hour=17, completed=True)
        _make_instance(db, family.id, sadie.id, sadie_routines[2].id, target, due_hour=21, completed=False)

        win = compute_daily_win(db, family.id, sadie.id, target)

        assert win.is_win is False
        assert win.task_count == 3
        assert win.completed_count == 2

    def test_completed_after_deadline_is_not_win(self, db: Session, family, children, sadie_routines):
        sadie = children["sadie"]
        target = date(2026, 3, 30)

        _make_instance(db, family.id, sadie.id, sadie_routines[0].id, target, due_hour=8, completed=True)
        _make_instance(db, family.id, sadie.id, sadie_routines[1].id, target, due_hour=17, completed=True)
        _make_instance(db, family.id, sadie.id, sadie_routines[2].id, target, due_hour=21, completed=True, completed_before_deadline=False)

        win = compute_daily_win(db, family.id, sadie.id, target)

        assert win.is_win is False
        assert win.completed_count == 3  # all completed, but one was late


class TestParentOverride:
    def test_override_true_counts_as_completed(self, db: Session, family, children, adults, sadie_routines):
        sadie = children["sadie"]
        robert = adults["robert"]
        target = date(2026, 3, 30)

        _make_instance(db, family.id, sadie.id, sadie_routines[0].id, target, due_hour=8, completed=True)
        _make_instance(db, family.id, sadie.id, sadie_routines[1].id, target, due_hour=17, completed=True)
        _make_instance(
            db, family.id, sadie.id, sadie_routines[2].id, target, due_hour=21,
            completed=False, override_completed=True, override_by=robert.id,
        )

        win = compute_daily_win(db, family.id, sadie.id, target)

        assert win.is_win is True
        assert win.completed_count == 3


class TestWeekendSkip:
    def test_weekend_returns_empty(self, db: Session, family, children):
        saturday = date(2026, 4, 4)
        result = compute_for_family_date(db, family.id, saturday)
        assert result == []

    def test_sunday_returns_empty(self, db: Session, family, children):
        sunday = date(2026, 4, 5)
        result = compute_for_family_date(db, family.id, sunday)
        assert result == []
