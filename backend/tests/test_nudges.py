"""Sprint 05 Phase 1 - nudges engine tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.personal_tasks import PersonalTask
from app.services import nudges_service


def _utcnow() -> datetime:
    # tz-aware; compare-safe against Postgres-hydrated timestamptz values
    return datetime.now(timezone.utc)


class TestScanOverdueTasks:
    def test_overdue_task_produces_one_proposal_for_the_assignee(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
        task = PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="Take out the trash",
            status="pending",
            due_at=now - timedelta(hours=1),
        )
        db.add(task)
        db.commit()

        proposals = nudges_service.scan_overdue_tasks(db, now)

        assert len(proposals) == 1
        p = proposals[0]
        assert p.family_member_id == andrew.id
        assert p.trigger_kind == "overdue_task"
        assert p.trigger_entity_kind == "personal_task"
        assert p.trigger_entity_id == task.id
        assert p.context["title"] == "Take out the trash"
        assert p.severity == "normal"

    def test_completed_task_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Already done",
                status="done",
                due_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=1),
            )
        )
        db.commit()

        assert nudges_service.scan_overdue_tasks(db, now) == []

    def test_future_task_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Later",
                status="pending",
                due_at=now + timedelta(hours=3),
            )
        )
        db.commit()

        assert nudges_service.scan_overdue_tasks(db, now) == []
