"""Family projects routes.

Permission model:

- `projects.create` gates POST /api/projects.
- `projects.manage_any` gates any mutation on any project in the family.
- `projects.manage_own` gates mutations on projects whose
  `primary_owner_family_member_id` equals the actor's member id.
- `project_tasks.update_assigned` gates status / notes updates on a
  task owned by the actor. Other fields (reassign, budget, reparent)
  still require `projects.manage_own` or `projects.manage_any`.
- `projects.view` gates all read routes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import FamilyMember
from app.models.projects import (
    Project,
    ProjectBudgetEntry,
    ProjectMilestone,
    ProjectTask,
)
from app.services import project_aggregation, project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Pydantic contracts
# ---------------------------------------------------------------------------

ProjectCategory = Literal[
    "birthday", "holiday", "trip", "school_event", "home_project", "weekend_reset", "custom"
]
ProjectStatus = Literal["draft", "active", "paused", "complete", "cancelled"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "skipped"]


class ProjectCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: ProjectCategory
    start_date: date
    description: str | None = None
    target_end_date: date | None = None
    budget_cents: int | None = Field(default=None, ge=0)
    primary_owner_family_member_id: uuid.UUID | None = None
    project_template_id: uuid.UUID | None = None
    name_override: str | None = None
    status: ProjectStatus = "draft"


class ProjectUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    category: ProjectCategory | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    target_end_date: date | None = None
    actual_end_date: date | None = None
    budget_cents: int | None = None
    primary_owner_family_member_id: uuid.UUID | None = None


class ProjectRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    project_template_id: uuid.UUID | None
    name: str
    description: str | None
    category: str
    status: str
    start_date: date
    target_end_date: date | None
    actual_end_date: date | None
    budget_cents: int | None
    actual_spent_cents: int | None
    primary_owner_family_member_id: uuid.UUID | None
    created_by_family_member_id: uuid.UUID
    created_at: datetime

    @classmethod
    def from_row(cls, row: Project) -> "ProjectRead":
        return cls(
            id=row.id,
            family_id=row.family_id,
            project_template_id=row.project_template_id,
            name=row.name,
            description=row.description,
            category=row.category,
            status=row.status,
            start_date=row.start_date,
            target_end_date=row.target_end_date,
            actual_end_date=row.actual_end_date,
            budget_cents=row.budget_cents,
            actual_spent_cents=row.actual_spent_cents,
            primary_owner_family_member_id=row.primary_owner_family_member_id,
            created_by_family_member_id=row.created_by_family_member_id,
            created_at=row.created_at,
        )


class ProjectTaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    owner_family_member_id: uuid.UUID | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    budget_cents: int | None = Field(default=None, ge=0)
    depends_on_project_task_id: uuid.UUID | None = None


class ProjectTaskUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    owner_family_member_id: uuid.UUID | None = None
    due_date: date | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    actual_duration_minutes: int | None = Field(default=None, ge=0)
    budget_cents: int | None = Field(default=None, ge=0)
    spent_cents: int | None = Field(default=None, ge=0)
    depends_on_project_task_id: uuid.UUID | None = None
    notes: str | None = None


class ProjectTaskRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    owner_family_member_id: uuid.UUID | None
    due_date: date | None
    estimated_duration_minutes: int | None
    actual_duration_minutes: int | None
    budget_cents: int | None
    spent_cents: int | None
    depends_on_project_task_id: uuid.UUID | None
    notes: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, r: ProjectTask) -> "ProjectTaskRead":
        return cls(
            id=r.id, project_id=r.project_id, title=r.title, description=r.description,
            status=r.status, owner_family_member_id=r.owner_family_member_id,
            due_date=r.due_date, estimated_duration_minutes=r.estimated_duration_minutes,
            actual_duration_minutes=r.actual_duration_minutes, budget_cents=r.budget_cents,
            spent_cents=r.spent_cents,
            depends_on_project_task_id=r.depends_on_project_task_id, notes=r.notes,
            created_at=r.created_at,
        )


class MilestoneCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_date: date
    order_index: int = 0
    notes: str | None = None


class MilestoneRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    target_date: date
    is_complete: bool
    completed_at: datetime | None
    order_index: int
    notes: str | None

    @classmethod
    def from_row(cls, r: ProjectMilestone) -> "MilestoneRead":
        return cls(
            id=r.id, project_id=r.project_id, name=r.name, target_date=r.target_date,
            is_complete=r.is_complete, completed_at=r.completed_at,
            order_index=r.order_index, notes=r.notes,
        )


class BudgetEntryCreateIn(BaseModel):
    amount_cents: int
    kind: Literal["estimate", "expense", "refund"]
    project_task_id: uuid.UUID | None = None
    vendor: str | None = None
    notes: str | None = None


class BudgetEntryRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_task_id: uuid.UUID | None
    amount_cents: int
    kind: str
    vendor: str | None
    notes: str | None
    recorded_at: datetime
    recorded_by_family_member_id: uuid.UUID

    @classmethod
    def from_row(cls, r: ProjectBudgetEntry) -> "BudgetEntryRead":
        return cls(
            id=r.id, project_id=r.project_id, project_task_id=r.project_task_id,
            amount_cents=r.amount_cents, kind=r.kind, vendor=r.vendor, notes=r.notes,
            recorded_at=r.recorded_at,
            recorded_by_family_member_id=r.recorded_by_family_member_id,
        )


class ProjectDetailRead(BaseModel):
    project: ProjectRead
    tasks: list[ProjectTaskRead]
    milestones: list[MilestoneRead]
    budget_entries: list[BudgetEntryRead]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_project_in_family(db: Session, project_id: uuid.UUID, family_id: uuid.UUID) -> Project:
    p = db.get(Project, project_id)
    if p is None or p.family_id != family_id:
        raise HTTPException(status_code=404, detail="project not found")
    return p


def _authorize_project_mutation(actor: Actor, project: Project) -> None:
    """Require manage_any, or manage_own when actor is the primary owner."""
    if actor.has_permission("projects.manage_any"):
        return
    if (
        project.primary_owner_family_member_id is not None
        and project.primary_owner_family_member_id == actor.member_id
        and actor.has_permission("projects.manage_own")
    ):
        return
    raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN,
                        detail="Permission required: projects.manage_any or projects.manage_own")


# ---------------------------------------------------------------------------
# Project CRUD + listing
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProjectRead])
def list_projects(
    project_status: str = "active",
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[ProjectRead]:
    actor.require_permission("projects.view")
    if actor.has_permission("projects.manage_any"):
        rows = project_aggregation.list_active_projects(db, actor.family_id)
    else:
        rows = project_aggregation.list_active_projects_for_family_member(
            db, actor.family_id, actor.member_id
        )
    if project_status != "all":
        rows = [r for r in rows if r.status == project_status or (project_status == "active" and r.status in ("active", "draft"))]
    return [ProjectRead.from_row(r) for r in rows]


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(
    payload: ProjectCreateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ProjectRead:
    actor.require_permission("projects.create")
    if payload.project_template_id is not None:
        project = project_service.create_from_template(
            db,
            family_id=actor.family_id,
            created_by_family_member_id=actor.member_id,
            project_template_id=payload.project_template_id,
            start_date=payload.start_date,
            name_override=payload.name_override or payload.name,
            primary_owner_family_member_id=payload.primary_owner_family_member_id,
        )
    else:
        project = project_service.create_blank(
            db,
            family_id=actor.family_id,
            created_by_family_member_id=actor.member_id,
            name=payload.name,
            category=payload.category,
            start_date=payload.start_date,
            description=payload.description,
            target_end_date=payload.target_end_date,
            budget_cents=payload.budget_cents,
            primary_owner_family_member_id=payload.primary_owner_family_member_id,
            status=payload.status,
        )
    db.commit()
    db.refresh(project)
    return ProjectRead.from_row(project)


@router.get("/{project_id}", response_model=ProjectDetailRead)
def get_project(
    project_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ProjectDetailRead:
    actor.require_permission("projects.view")
    project = _load_project_in_family(db, project_id, actor.family_id)

    tasks = (
        db.execute(
            select(ProjectTask)
            .where(ProjectTask.project_id == project.id)
            .order_by(ProjectTask.due_date.asc().nullslast(), ProjectTask.created_at)
        )
        .scalars()
        .all()
    )
    milestones = (
        db.execute(
            select(ProjectMilestone)
            .where(ProjectMilestone.project_id == project.id)
            .order_by(ProjectMilestone.target_date.asc())
        )
        .scalars()
        .all()
    )
    entries = (
        db.execute(
            select(ProjectBudgetEntry)
            .where(ProjectBudgetEntry.project_id == project.id)
            .order_by(ProjectBudgetEntry.recorded_at.desc())
        )
        .scalars()
        .all()
    )
    return ProjectDetailRead(
        project=ProjectRead.from_row(project),
        tasks=[ProjectTaskRead.from_row(t) for t in tasks],
        milestones=[MilestoneRead.from_row(m) for m in milestones],
        budget_entries=[BudgetEntryRead.from_row(b) for b in entries],
    )


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ProjectRead:
    actor.require_permission("projects.manage_own")
    project = _load_project_in_family(db, project_id, actor.family_id)
    _authorize_project_mutation(actor, project)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(project, k, v)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return ProjectRead.from_row(project)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

_ASSIGNED_EDITABLE_FIELDS = {"status", "notes"}


@router.post("/{project_id}/tasks", response_model=ProjectTaskRead, status_code=201)
def add_task(
    project_id: uuid.UUID,
    payload: ProjectTaskCreateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ProjectTaskRead:
    actor.require_permission("projects.manage_own")
    project = _load_project_in_family(db, project_id, actor.family_id)
    _authorize_project_mutation(actor, project)
    task = project_service.add_task(
        db, project_id=project.id, **payload.model_dump()
    )
    db.commit()
    db.refresh(task)
    return ProjectTaskRead.from_row(task)


@router.patch("/{project_id}/tasks/{task_id}", response_model=ProjectTaskRead)
def update_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: ProjectTaskUpdateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ProjectTaskRead:
    # Either update-assigned (kid-tier on their own task) or manage_own/any
    # will satisfy the in-body branching below. Both keys exist on every
    # non-DISPLAY tier, so this top-level check acts as a floor.
    actor.require_permission("project_tasks.update_assigned")
    project = _load_project_in_family(db, project_id, actor.family_id)
    task = db.get(ProjectTask, task_id)
    if task is None or task.project_id != project.id:
        raise HTTPException(status_code=404, detail="task not found")

    data = payload.model_dump(exclude_unset=True)
    touched = set(data.keys())

    can_manage = actor.has_permission("projects.manage_any") or (
        project.primary_owner_family_member_id == actor.member_id
        and actor.has_permission("projects.manage_own")
    )
    is_assignee = task.owner_family_member_id == actor.member_id
    can_update_assigned = is_assignee and actor.has_permission("project_tasks.update_assigned")

    if not can_manage:
        if not (can_update_assigned and touched.issubset(_ASSIGNED_EDITABLE_FIELDS)):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail=(
                    "Permission required: projects.manage_any or projects.manage_own, "
                    "or project_tasks.update_assigned for status/notes on your own task"
                ),
            )

    for k, v in data.items():
        setattr(task, k, v)
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return ProjectTaskRead.from_row(task)


@router.post("/{project_id}/tasks/{task_id}/promote", status_code=201)
def promote_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    actor.require_permission("projects.manage_own")
    project = _load_project_in_family(db, project_id, actor.family_id)
    _authorize_project_mutation(actor, project)
    task = db.get(ProjectTask, task_id)
    if task is None or task.project_id != project.id:
        raise HTTPException(status_code=404, detail="task not found")
    try:
        pt = project_service.promote_project_task_to_personal_task(
            db,
            project_task=task,
            family_id=actor.family_id,
            created_by_family_member_id=actor.member_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"personal_task_id": str(pt.id), "source_project_task_id": str(task.id)}


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

@router.post("/{project_id}/milestones", response_model=MilestoneRead, status_code=201)
def add_milestone(
    project_id: uuid.UUID,
    payload: MilestoneCreateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> MilestoneRead:
    actor.require_permission("projects.manage_own")
    project = _load_project_in_family(db, project_id, actor.family_id)
    _authorize_project_mutation(actor, project)
    m = project_service.add_milestone(db, project_id=project.id, **payload.model_dump())
    db.commit()
    db.refresh(m)
    return MilestoneRead.from_row(m)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

@router.post("/{project_id}/budget", response_model=BudgetEntryRead, status_code=201)
def add_budget_entry(
    project_id: uuid.UUID,
    payload: BudgetEntryCreateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BudgetEntryRead:
    actor.require_permission("projects.manage_own")
    project = _load_project_in_family(db, project_id, actor.family_id)
    _authorize_project_mutation(actor, project)
    e = project_service.add_budget_entry(
        db,
        project_id=project.id,
        recorded_by_family_member_id=actor.member_id,
        **payload.model_dump(),
    )
    db.commit()
    db.refresh(e)
    return BudgetEntryRead.from_row(e)


# ---------------------------------------------------------------------------
# Health summary
# ---------------------------------------------------------------------------

@router.get("/today/me", response_model=list[ProjectTaskRead])
def my_project_tasks_today(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[ProjectTaskRead]:
    """Project tasks assigned to the current actor that are due on or
    before today. Independent of promotion to personal_tasks."""
    actor.require_permission("projects.view")
    rows = project_aggregation.list_due_project_tasks_for_today(
        db, family_member_id=actor.member_id, family_id=actor.family_id
    )
    return [ProjectTaskRead.from_row(r) for r in rows]


@router.get("/{project_id}/health")
def project_health(
    project_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    actor.require_permission("projects.view")
    project = _load_project_in_family(db, project_id, actor.family_id)
    return project_aggregation.project_health_summary(db, project.id)
