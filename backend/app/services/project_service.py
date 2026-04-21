"""Family projects engine — write-side service.

Project tasks are the source of truth. Promoting a project task into
a personal_tasks row is optional convenience; edits to the promoted
row do not mutate the project task.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.personal_tasks import PersonalTask
from app.models.projects import (
    Project,
    ProjectBudgetEntry,
    ProjectMilestone,
    ProjectTask,
    ProjectTemplate,
    ProjectTemplateTask,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Template management
# ---------------------------------------------------------------------------

def create_template(
    db: Session,
    *,
    family_id: uuid.UUID,
    created_by_family_member_id: uuid.UUID,
    name: str,
    category: str,
    description: str | None = None,
    estimated_duration_days: int | None = None,
    default_lead_time_days: int = 0,
    default_budget_cents: int | None = None,
) -> ProjectTemplate:
    tpl = ProjectTemplate(
        family_id=family_id,
        created_by_family_member_id=created_by_family_member_id,
        name=name,
        description=description,
        category=category,
        estimated_duration_days=estimated_duration_days,
        default_lead_time_days=default_lead_time_days,
        default_budget_cents=default_budget_cents,
    )
    db.add(tpl)
    db.flush()
    return tpl


def add_template_task(
    db: Session,
    *,
    template_id: uuid.UUID,
    title: str,
    description: str | None = None,
    order_index: int = 0,
    relative_day_offset: int = 0,
    default_owner_role: str | None = None,
    estimated_duration_minutes: int | None = None,
    has_budget_impact: bool = False,
    has_grocery_impact: bool = False,
) -> ProjectTemplateTask:
    t = ProjectTemplateTask(
        project_template_id=template_id,
        title=title,
        description=description,
        order_index=order_index,
        relative_day_offset=relative_day_offset,
        default_owner_role=default_owner_role,
        estimated_duration_minutes=estimated_duration_minutes,
        has_budget_impact=has_budget_impact,
        has_grocery_impact=has_grocery_impact,
    )
    db.add(t)
    db.flush()
    return t


# ---------------------------------------------------------------------------
# Project creation
# ---------------------------------------------------------------------------

def create_blank(
    db: Session,
    *,
    family_id: uuid.UUID,
    created_by_family_member_id: uuid.UUID,
    name: str,
    category: str,
    start_date: date,
    description: str | None = None,
    target_end_date: date | None = None,
    budget_cents: int | None = None,
    primary_owner_family_member_id: uuid.UUID | None = None,
    status: str = "draft",
) -> Project:
    project = Project(
        family_id=family_id,
        name=name,
        description=description,
        category=category,
        status=status,
        start_date=start_date,
        target_end_date=target_end_date,
        budget_cents=budget_cents,
        primary_owner_family_member_id=primary_owner_family_member_id,
        created_by_family_member_id=created_by_family_member_id,
    )
    db.add(project)
    db.flush()
    return project


def create_from_template(
    db: Session,
    *,
    family_id: uuid.UUID,
    created_by_family_member_id: uuid.UUID,
    project_template_id: uuid.UUID,
    start_date: date,
    name_override: str | None = None,
    primary_owner_family_member_id: uuid.UUID | None = None,
) -> Project:
    tpl = db.get(ProjectTemplate, project_template_id)
    if tpl is None or (tpl.family_id is not None and tpl.family_id != family_id):
        raise ValueError("template not found in your family")

    project = Project(
        family_id=family_id,
        project_template_id=tpl.id,
        name=name_override or tpl.name,
        description=tpl.description,
        category=tpl.category,
        status="draft",
        start_date=start_date,
        target_end_date=(
            start_date + timedelta(days=tpl.estimated_duration_days)
            if tpl.estimated_duration_days
            else None
        ),
        budget_cents=tpl.default_budget_cents,
        primary_owner_family_member_id=primary_owner_family_member_id,
        created_by_family_member_id=created_by_family_member_id,
    )
    db.add(project)
    db.flush()
    instantiate_template_tasks(db, project=project, template=tpl)
    return project


def instantiate_template_tasks(
    db: Session, *, project: Project, template: ProjectTemplate
) -> list[ProjectTask]:
    template_tasks = (
        db.execute(
            select(ProjectTemplateTask)
            .where(ProjectTemplateTask.project_template_id == template.id)
            .order_by(ProjectTemplateTask.order_index, ProjectTemplateTask.created_at)
        )
        .scalars()
        .all()
    )
    created: list[ProjectTask] = []
    for tt in template_tasks:
        pt = ProjectTask(
            project_id=project.id,
            title=tt.title,
            description=tt.description,
            due_date=project.start_date + timedelta(days=tt.relative_day_offset),
            estimated_duration_minutes=tt.estimated_duration_minutes,
        )
        db.add(pt)
        created.append(pt)
    db.flush()
    return created


# ---------------------------------------------------------------------------
# Task / milestone / budget mutations
# ---------------------------------------------------------------------------

def add_task(
    db: Session,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str | None = None,
    due_date: date | None = None,
    owner_family_member_id: uuid.UUID | None = None,
    estimated_duration_minutes: int | None = None,
    budget_cents: int | None = None,
    depends_on_project_task_id: uuid.UUID | None = None,
) -> ProjectTask:
    task = ProjectTask(
        project_id=project_id,
        title=title,
        description=description,
        due_date=due_date,
        owner_family_member_id=owner_family_member_id,
        estimated_duration_minutes=estimated_duration_minutes,
        budget_cents=budget_cents,
        depends_on_project_task_id=depends_on_project_task_id,
    )
    db.add(task)
    db.flush()
    return task


def complete_task(
    db: Session,
    *,
    task: ProjectTask,
    actual_duration_minutes: int | None = None,
) -> ProjectTask:
    task.status = "done"
    if actual_duration_minutes is not None:
        task.actual_duration_minutes = actual_duration_minutes
    task.updated_at = _utcnow()
    db.flush()
    return task


def add_milestone(
    db: Session,
    *,
    project_id: uuid.UUID,
    name: str,
    target_date: date,
    order_index: int = 0,
    notes: str | None = None,
) -> ProjectMilestone:
    m = ProjectMilestone(
        project_id=project_id,
        name=name,
        target_date=target_date,
        order_index=order_index,
        notes=notes,
    )
    db.add(m)
    db.flush()
    return m


def complete_milestone(db: Session, *, milestone: ProjectMilestone) -> ProjectMilestone:
    milestone.is_complete = True
    milestone.completed_at = _utcnow()
    milestone.updated_at = _utcnow()
    db.flush()
    return milestone


def add_budget_entry(
    db: Session,
    *,
    project_id: uuid.UUID,
    recorded_by_family_member_id: uuid.UUID,
    amount_cents: int,
    kind: str,
    project_task_id: uuid.UUID | None = None,
    vendor: str | None = None,
    notes: str | None = None,
) -> ProjectBudgetEntry:
    e = ProjectBudgetEntry(
        project_id=project_id,
        project_task_id=project_task_id,
        amount_cents=amount_cents,
        kind=kind,
        vendor=vendor,
        notes=notes,
        recorded_by_family_member_id=recorded_by_family_member_id,
    )
    db.add(e)
    db.flush()
    return e


def promote_project_task_to_personal_task(
    db: Session,
    *,
    project_task: ProjectTask,
    family_id: uuid.UUID,
    created_by_family_member_id: uuid.UUID,
) -> PersonalTask:
    """Copy a project task into personal_tasks. One-way — the project
    task remains the source of truth. Idempotent via the unique index
    on source_project_task_id."""
    existing = db.execute(
        select(PersonalTask).where(PersonalTask.source_project_task_id == project_task.id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    if project_task.owner_family_member_id is None:
        raise ValueError("cannot promote an unassigned project task")

    due_at = None
    if project_task.due_date is not None:
        due_at = datetime.combine(project_task.due_date, datetime.min.time())

    pt = PersonalTask(
        family_id=family_id,
        assigned_to=project_task.owner_family_member_id,
        created_by=created_by_family_member_id,
        title=project_task.title,
        description=project_task.description,
        status="pending",
        priority="medium",
        due_at=due_at,
        source_project_task_id=project_task.id,
    )
    db.add(pt)
    db.flush()
    return pt
