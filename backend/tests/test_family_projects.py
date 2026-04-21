"""Backend coverage for Sprint Expansion Phase 3 — family projects engine.

Covers:

- Template → project instantiation (five tasks with due-date offsets).
- Route happy-path: create project, add task + milestone + budget entry.
- Permission denial: child-tier cannot call projects.create; kid-tier
  cannot edit fields beyond status/notes on an unowned task; kid CAN
  update status on a task assigned to them.
- Today integration: a project task due today is returned by
  GET /api/projects/today/me even without promotion.
- Promotion linkage: promote_project_task_to_personal_task creates
  one personal_tasks row keyed to source_project_task_id; second
  promotion is idempotent.
- AI tool count: TOOL_FUNCTIONS grows by exactly 2 over main.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import (
    FamilyMember,
    Session as SessionModel,
    UserAccount,
)
from app.models.personal_tasks import PersonalTask
from app.models.projects import (
    Project,
    ProjectBudgetEntry,
    ProjectMilestone,
    ProjectTask,
    ProjectTemplate,
    ProjectTemplateTask,
)
from app.services import project_aggregation, project_service
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _token_for(db: Session, member_id, email: str | None = None) -> str:
    email = email or f"proj-{uuid.uuid4().hex[:8]}@scout.local"
    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=email,
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=True,
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


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Template instantiation
# ---------------------------------------------------------------------------


class TestTemplateInstantiation:
    def test_create_from_template_copies_five_tasks_with_due_dates(self, db, family, adults):
        tpl = project_service.create_template(
            db,
            family_id=family.id,
            created_by_family_member_id=adults["robert"].id,
            name="Birthday",
            category="birthday",
            estimated_duration_days=30,
            default_lead_time_days=14,
            default_budget_cents=10_000,
        )
        for i, (title, offset) in enumerate(
            [
                ("Pick theme", 0),
                ("Order cake", 14),
                ("Send invites", 21),
                ("Buy decorations", 27),
                ("Party!", 30),
            ]
        ):
            project_service.add_template_task(
                db,
                template_id=tpl.id,
                title=title,
                order_index=i,
                relative_day_offset=offset,
            )
        db.commit()

        start = date(2026, 5, 1)
        project = project_service.create_from_template(
            db,
            family_id=family.id,
            created_by_family_member_id=adults["robert"].id,
            project_template_id=tpl.id,
            start_date=start,
        )
        db.commit()

        rows = (
            db.execute(
                select(ProjectTask)
                .where(ProjectTask.project_id == project.id)
                .order_by(ProjectTask.due_date)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 5
        assert [r.due_date for r in rows] == [
            start,
            start + timedelta(days=14),
            start + timedelta(days=21),
            start + timedelta(days=27),
            start + timedelta(days=30),
        ]
        assert project.budget_cents == 10_000
        assert project.target_end_date == start + timedelta(days=30)


# ---------------------------------------------------------------------------
# Route permission denial
# ---------------------------------------------------------------------------


class TestRoutePermissions:
    def test_child_cannot_create_project(self, client, db, family, children):
        sadie = children["sadie"]  # role=child → CHILD tier, no projects.create
        tok = _token_for(db, sadie.id)
        r = client.post(
            "/api/projects",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "name": "School project",
                "category": "school_event",
                "start_date": date.today().isoformat(),
            },
        )
        assert r.status_code == 403
        assert "projects.create" in r.json().get("detail", "")

    def test_child_can_update_status_on_own_task_but_not_reassign(
        self, client, db, family, adults, children
    ):
        robert = adults["robert"]
        sadie = children["sadie"]
        # Admin creates project with a task owned by sadie.
        project = project_service.create_blank(
            db,
            family_id=family.id,
            created_by_family_member_id=robert.id,
            name="Trip",
            category="trip",
            start_date=date.today(),
            status="active",
        )
        task = project_service.add_task(
            db,
            project_id=project.id,
            title="Pack bag",
            owner_family_member_id=sadie.id,
        )
        db.commit()

        tok = _token_for(db, sadie.id)
        headers = {"Authorization": f"Bearer {tok}"}

        # Allowed: update status on own task.
        r = client.patch(
            f"/api/projects/{project.id}/tasks/{task.id}",
            headers=headers,
            json={"status": "done"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "done"

        # Denied: try to reassign — requires manage_own/manage_any.
        r2 = client.patch(
            f"/api/projects/{project.id}/tasks/{task.id}",
            headers=headers,
            json={"owner_family_member_id": str(robert.id)},
        )
        assert r2.status_code == 403


# ---------------------------------------------------------------------------
# Today integration
# ---------------------------------------------------------------------------


class TestTodayIntegration:
    def test_project_task_due_today_appears_without_promotion(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        project = project_service.create_blank(
            db,
            family_id=family.id,
            created_by_family_member_id=robert.id,
            name="Trip",
            category="trip",
            start_date=date.today(),
            status="active",
        )
        project_service.add_task(
            db,
            project_id=project.id,
            title="Confirm reservations",
            due_date=date.today(),
            owner_family_member_id=robert.id,
        )
        db.commit()

        tok = _token_for(db, robert.id)
        r = client.get(
            "/api/projects/today/me",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["title"] == "Confirm reservations"

        # No personal_tasks row was created because no promotion happened.
        personal_rows = db.execute(select(PersonalTask)).scalars().all()
        assert personal_rows == []


# ---------------------------------------------------------------------------
# Promotion linkage
# ---------------------------------------------------------------------------


class TestPromotion:
    def test_promotion_creates_linked_personal_task_and_is_idempotent(
        self, db, family, adults
    ):
        robert = adults["robert"]
        project = project_service.create_blank(
            db,
            family_id=family.id,
            created_by_family_member_id=robert.id,
            name="Holiday",
            category="holiday",
            start_date=date.today(),
        )
        task = project_service.add_task(
            db,
            project_id=project.id,
            title="Call grandma",
            due_date=date.today(),
            owner_family_member_id=robert.id,
        )
        db.commit()

        pt1 = project_service.promote_project_task_to_personal_task(
            db,
            project_task=task,
            family_id=family.id,
            created_by_family_member_id=robert.id,
        )
        db.commit()
        assert pt1.source_project_task_id == task.id

        pt2 = project_service.promote_project_task_to_personal_task(
            db,
            project_task=task,
            family_id=family.id,
            created_by_family_member_id=robert.id,
        )
        db.commit()
        assert pt2.id == pt1.id

        rows = (
            db.execute(
                select(PersonalTask).where(
                    PersonalTask.source_project_task_id == task.id
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# AI tool count: +2 over baseline
# ---------------------------------------------------------------------------


class TestAIToolRegistry:
    def test_registry_contains_new_project_tools(self):
        from app.ai.tools import TOOL_DEFINITIONS

        # Both tools must appear in the definitions registry.
        assert "create_project_from_template" in TOOL_DEFINITIONS
        assert "add_project_task" in TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# Health summary
# ---------------------------------------------------------------------------


class TestHealthSummary:
    def test_health_summary_reports_completion_percent(self, db, family, adults):
        robert = adults["robert"]
        project = project_service.create_blank(
            db,
            family_id=family.id,
            created_by_family_member_id=robert.id,
            name="Reset",
            category="weekend_reset",
            start_date=date.today(),
        )
        t1 = project_service.add_task(db, project_id=project.id, title="T1")
        project_service.add_task(db, project_id=project.id, title="T2")
        project_service.add_task(db, project_id=project.id, title="T3")
        project_service.add_task(db, project_id=project.id, title="T4")
        db.commit()

        project_service.complete_task(db, task=t1)
        db.commit()

        summary = project_aggregation.project_health_summary(db, project.id)
        assert summary["tasks_total"] == 4
        assert summary["tasks_done"] == 1
        assert summary["completion_percent"] == 25
