"""Family projects — read-side aggregation.

Today integration queries `project_tasks` directly by
`owner_family_member_id` + `due_date`. Promotion is optional;
un-promoted tasks still appear on Today.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.projects import Project, ProjectMilestone, ProjectTask


def list_active_projects(db: Session, family_id: uuid.UUID) -> list[Project]:
    return (
        db.execute(
            select(Project)
            .where(
                Project.family_id == family_id,
                Project.status.in_(["active", "draft"]),
            )
            .order_by(Project.start_date.asc())
        )
        .scalars()
        .all()
    )


def list_active_projects_for_family_member(
    db: Session, family_id: uuid.UUID, family_member_id: uuid.UUID
) -> list[Project]:
    """Projects a kid-tier user should see: ones they own OR that have
    at least one task assigned to them."""
    owned = (
        select(Project)
        .where(
            Project.family_id == family_id,
            Project.primary_owner_family_member_id == family_member_id,
            Project.status.in_(["active", "draft"]),
        )
    )
    assigned = (
        select(Project)
        .join(ProjectTask, ProjectTask.project_id == Project.id)
        .where(
            Project.family_id == family_id,
            ProjectTask.owner_family_member_id == family_member_id,
            Project.status.in_(["active", "draft"]),
        )
        .distinct()
    )
    rows = db.execute(owned.union(assigned)).all()
    seen: dict[uuid.UUID, Project] = {}
    for r in rows:
        p = db.get(Project, r[0])
        if p is not None and p.id not in seen:
            seen[p.id] = p
    return sorted(seen.values(), key=lambda p: p.start_date)


def project_health_summary(db: Session, project_id: uuid.UUID) -> dict[str, Any]:
    total = db.scalar(
        select(func.count()).select_from(ProjectTask).where(ProjectTask.project_id == project_id)
    ) or 0
    done = db.scalar(
        select(func.count())
        .select_from(ProjectTask)
        .where(ProjectTask.project_id == project_id, ProjectTask.status == "done")
    ) or 0
    overdue_today = date.today()
    overdue = db.scalar(
        select(func.count())
        .select_from(ProjectTask)
        .where(
            ProjectTask.project_id == project_id,
            ProjectTask.status != "done",
            ProjectTask.due_date.is_not(None),
            ProjectTask.due_date < overdue_today,
        )
    ) or 0
    blocked = db.scalar(
        select(func.count())
        .select_from(ProjectTask)
        .where(ProjectTask.project_id == project_id, ProjectTask.status == "blocked")
    ) or 0
    milestones_total = db.scalar(
        select(func.count())
        .select_from(ProjectMilestone)
        .where(ProjectMilestone.project_id == project_id)
    ) or 0
    milestones_complete = db.scalar(
        select(func.count())
        .select_from(ProjectMilestone)
        .where(
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.is_complete.is_(True),
        )
    ) or 0
    return {
        "project_id": str(project_id),
        "tasks_total": int(total),
        "tasks_done": int(done),
        "tasks_overdue": int(overdue),
        "tasks_blocked": int(blocked),
        "completion_percent": (int(done) * 100 // int(total)) if total else 0,
        "milestones_total": int(milestones_total),
        "milestones_complete": int(milestones_complete),
    }


def list_due_project_tasks_for_today(
    db: Session, family_member_id: uuid.UUID, family_id: uuid.UUID, as_of: date | None = None
) -> list[ProjectTask]:
    """Tasks due on or before today, assigned to this member, for active
    projects in the member's family. Independent of whether the task was
    promoted to personal_tasks."""
    as_of = as_of or date.today()
    return (
        db.execute(
            select(ProjectTask)
            .join(Project, Project.id == ProjectTask.project_id)
            .where(
                Project.family_id == family_id,
                Project.status.in_(["active", "draft"]),
                ProjectTask.owner_family_member_id == family_member_id,
                ProjectTask.status.in_(["todo", "in_progress", "blocked"]),
                ProjectTask.due_date.is_not(None),
                ProjectTask.due_date <= as_of,
            )
            .order_by(ProjectTask.due_date.asc())
        )
        .scalars()
        .all()
    )
