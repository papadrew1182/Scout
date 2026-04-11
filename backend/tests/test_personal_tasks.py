"""Tests for personal_tasks_service.

Covers:
- create personal task
- status/priority validation
- completed_at consistency rule
- complete task transitions status to done and sets completed_at
- list with filters (incomplete, due window)
- top N query (priority + due ordering)
- due-today helper
- tenant isolation
"""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
import pytz
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember
from app.models.personal_tasks import PersonalTask
from app.schemas.personal_tasks import PersonalTaskCreate, PersonalTaskUpdate
from app.services.personal_tasks_service import (
    complete_personal_task,
    create_personal_task,
    delete_personal_task,
    get_personal_task,
    list_due_today,
    list_personal_tasks,
    list_top_personal_tasks,
    update_personal_task,
)


def _dt(y, m, d, h=12, minute=0):
    return pytz.timezone("America/Chicago").localize(datetime(y, m, d, h, minute))


class TestCreate:
    def test_create_basic(self, db: Session, family, adults):
        andrew = adults["robert"]
        task = create_personal_task(
            db, family.id,
            PersonalTaskCreate(
                assigned_to=andrew.id,
                created_by=andrew.id,
                title="Submit expense report",
                priority="urgent",
                due_at=_dt(2026, 4, 9, 17),
            ),
        )
        assert task.id is not None
        assert task.status == "pending"
        assert task.completed_at is None
        assert task.priority == "urgent"

    def test_create_done_sets_completed_at(self, db: Session, family, adults):
        andrew = adults["robert"]
        task = create_personal_task(
            db, family.id,
            PersonalTaskCreate(
                assigned_to=andrew.id,
                title="Already done",
                status="done",
            ),
        )
        assert task.status == "done"
        assert task.completed_at is not None

    def test_invalid_status_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            create_personal_task(
                db, family.id,
                PersonalTaskCreate(
                    assigned_to=adults["robert"].id,
                    title="Bad",
                    status="floating",
                ),
            )
        assert exc.value.status_code == 400

    def test_invalid_priority_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            create_personal_task(
                db, family.id,
                PersonalTaskCreate(
                    assigned_to=adults["robert"].id,
                    title="Bad",
                    priority="critical",
                ),
            )
        assert exc.value.status_code == 400

    def test_db_completed_consistency_check(self, db: Session, family, adults):
        # Bypass service: trying to insert pending+completed_at directly should fail
        bad = PersonalTask(
            family_id=family.id,
            assigned_to=adults["robert"].id,
            title="Inconsistent",
            status="pending",
            priority="medium",
            completed_at=datetime.now().astimezone(),
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()


class TestUpdateAndComplete:
    def test_complete_transitions_status(self, db: Session, family, adults):
        andrew = adults["robert"]
        task = create_personal_task(
            db, family.id,
            PersonalTaskCreate(assigned_to=andrew.id, title="Do thing"),
        )
        completed = complete_personal_task(db, family.id, task.id)
        assert completed.status == "done"
        assert completed.completed_at is not None

    def test_update_status_to_done_sets_completed_at(self, db: Session, family, adults):
        andrew = adults["robert"]
        task = create_personal_task(
            db, family.id,
            PersonalTaskCreate(assigned_to=andrew.id, title="Do thing"),
        )
        updated = update_personal_task(
            db, family.id, task.id, PersonalTaskUpdate(status="done")
        )
        assert updated.status == "done"
        assert updated.completed_at is not None

    def test_update_done_to_pending_clears_completed_at(self, db: Session, family, adults):
        andrew = adults["robert"]
        task = create_personal_task(
            db, family.id,
            PersonalTaskCreate(assigned_to=andrew.id, title="Do thing", status="done"),
        )
        updated = update_personal_task(
            db, family.id, task.id, PersonalTaskUpdate(status="pending")
        )
        assert updated.status == "pending"
        assert updated.completed_at is None

    def test_delete(self, db: Session, family, adults):
        task = create_personal_task(
            db, family.id,
            PersonalTaskCreate(assigned_to=adults["robert"].id, title="X"),
        )
        delete_personal_task(db, family.id, task.id)
        with pytest.raises(HTTPException) as exc:
            get_personal_task(db, family.id, task.id)
        assert exc.value.status_code == 404


class TestListAndFilters:
    def test_incomplete_only(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_personal_task(db, family.id, PersonalTaskCreate(assigned_to=andrew.id, title="P", status="pending"))
        create_personal_task(db, family.id, PersonalTaskCreate(assigned_to=andrew.id, title="D", status="done"))
        create_personal_task(db, family.id, PersonalTaskCreate(assigned_to=andrew.id, title="C", status="cancelled"))

        results = list_personal_tasks(db, family.id, assigned_to=andrew.id, incomplete_only=True)
        titles = {t.title for t in results}
        assert titles == {"P"}

    def test_due_window(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Today", due_at=_dt(2026, 4, 9, 12)))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Next week", due_at=_dt(2026, 4, 16, 12)))

        results = list_personal_tasks(
            db, family.id,
            due_before=_dt(2026, 4, 10, 0),
        )
        titles = {t.title for t in results}
        assert "Today" in titles
        assert "Next week" not in titles


class TestTopTasks:
    def test_top_orders_by_priority_then_due(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Low later", priority="low", due_at=_dt(2026, 4, 20, 12)))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Urgent now", priority="urgent", due_at=_dt(2026, 4, 9, 12)))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="High later", priority="high", due_at=_dt(2026, 4, 15, 12)))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Medium nodue", priority="medium"))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Done one", priority="urgent", status="done"))

        results = list_top_personal_tasks(db, family.id, andrew.id, limit=5)
        titles = [t.title for t in results]
        # Order: urgent → high → medium → low. Done is excluded.
        assert titles == ["Urgent now", "High later", "Medium nodue", "Low later"]

    def test_top_excludes_done(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Active", priority="low"))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Done", priority="urgent", status="done"))

        results = list_top_personal_tasks(db, family.id, andrew.id)
        titles = {t.title for t in results}
        assert titles == {"Active"}

    def test_top_limit_respected(self, db: Session, family, adults):
        andrew = adults["robert"]
        for i in range(10):
            create_personal_task(db, family.id, PersonalTaskCreate(
                assigned_to=andrew.id, title=f"Task {i}", priority="medium"))

        results = list_top_personal_tasks(db, family.id, andrew.id, limit=5)
        assert len(results) == 5


class TestDueToday:
    def test_due_today_filter(self, db: Session, family, adults):
        andrew = adults["robert"]
        target = date(2026, 4, 9)
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Today AM", due_at=_dt(2026, 4, 9, 9)))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Today PM", due_at=_dt(2026, 4, 9, 17)))
        create_personal_task(db, family.id, PersonalTaskCreate(
            assigned_to=andrew.id, title="Tomorrow", due_at=_dt(2026, 4, 10, 9)))

        results = list_due_today(db, family.id, andrew.id, target)
        titles = {t.title for t in results}
        assert titles == {"Today AM", "Today PM"}


class TestTenantIsolation:
    def test_get_task_from_wrong_family_404(self, db: Session, family, adults):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(
            family_id=other.id, first_name="Stranger", role="adult"
        )
        db.add(other_member)
        db.flush()

        task = create_personal_task(
            db, other.id,
            PersonalTaskCreate(assigned_to=other_member.id, title="Theirs"),
        )
        with pytest.raises(HTTPException) as exc:
            get_personal_task(db, family.id, task.id)
        assert exc.value.status_code == 404

    def test_assigned_to_must_be_in_family(self, db: Session, family, adults):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(
            family_id=other.id, first_name="Stranger", role="adult"
        )
        db.add(other_member)
        db.flush()

        with pytest.raises(HTTPException) as exc:
            create_personal_task(
                db, family.id,
                PersonalTaskCreate(assigned_to=other_member.id, title="Bad assign"),
            )
        assert exc.value.status_code == 404
