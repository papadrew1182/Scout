"""Project templates — family-local CRUD.

Built-in / global templates (`is_builtin=true`, null family_id) are a
forward-looking concept; Phase 3 only wires family-local templates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.projects import ProjectTemplate, ProjectTemplateTask
from app.services import project_service

router = APIRouter(prefix="/api/project_templates", tags=["project_templates"])

TemplateCategory = Literal[
    "birthday", "holiday", "trip", "school_event", "home_project", "weekend_reset", "custom"
]


class TemplateCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: TemplateCategory
    description: str | None = None
    estimated_duration_days: int | None = Field(default=None, ge=0)
    default_lead_time_days: int = 0
    default_budget_cents: int | None = Field(default=None, ge=0)


class TemplateUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    category: TemplateCategory | None = None
    estimated_duration_days: int | None = None
    default_lead_time_days: int | None = None
    default_budget_cents: int | None = None
    is_active: bool | None = None


class TemplateRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID | None
    name: str
    description: str | None
    category: str
    estimated_duration_days: int | None
    default_lead_time_days: int
    default_budget_cents: int | None
    is_active: bool
    is_builtin: bool
    created_at: datetime

    @classmethod
    def from_row(cls, r: ProjectTemplate) -> "TemplateRead":
        return cls(
            id=r.id, family_id=r.family_id, name=r.name, description=r.description,
            category=r.category, estimated_duration_days=r.estimated_duration_days,
            default_lead_time_days=r.default_lead_time_days,
            default_budget_cents=r.default_budget_cents,
            is_active=r.is_active, is_builtin=r.is_builtin, created_at=r.created_at,
        )


class TemplateTaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order_index: int = 0
    relative_day_offset: int = 0
    default_owner_role: str | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    has_budget_impact: bool = False
    has_grocery_impact: bool = False


class TemplateTaskRead(BaseModel):
    id: uuid.UUID
    project_template_id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    relative_day_offset: int
    default_owner_role: str | None
    estimated_duration_minutes: int | None
    has_budget_impact: bool
    has_grocery_impact: bool

    @classmethod
    def from_row(cls, r: ProjectTemplateTask) -> "TemplateTaskRead":
        return cls(
            id=r.id, project_template_id=r.project_template_id, title=r.title,
            description=r.description, order_index=r.order_index,
            relative_day_offset=r.relative_day_offset, default_owner_role=r.default_owner_role,
            estimated_duration_minutes=r.estimated_duration_minutes,
            has_budget_impact=r.has_budget_impact, has_grocery_impact=r.has_grocery_impact,
        )


def _load_template_in_family(
    db: Session, template_id: uuid.UUID, family_id: uuid.UUID
) -> ProjectTemplate:
    t = db.get(ProjectTemplate, template_id)
    if t is None or (t.family_id is not None and t.family_id != family_id):
        raise HTTPException(status_code=404, detail="template not found")
    return t


@router.get("", response_model=list[TemplateRead])
def list_templates(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[TemplateRead]:
    actor.require_permission("project_templates.view")
    rows = (
        db.execute(
            select(ProjectTemplate)
            .where(
                (ProjectTemplate.family_id == actor.family_id)
                | (ProjectTemplate.is_builtin.is_(True))
            )
            .order_by(ProjectTemplate.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [TemplateRead.from_row(r) for r in rows]


@router.post("", response_model=TemplateRead, status_code=201)
def create_template(
    payload: TemplateCreateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> TemplateRead:
    actor.require_permission("project_templates.manage")
    tpl = project_service.create_template(
        db,
        family_id=actor.family_id,
        created_by_family_member_id=actor.member_id,
        **payload.model_dump(),
    )
    db.commit()
    db.refresh(tpl)
    return TemplateRead.from_row(tpl)


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(
    template_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> TemplateRead:
    actor.require_permission("project_templates.view")
    t = _load_template_in_family(db, template_id, actor.family_id)
    return TemplateRead.from_row(t)


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> TemplateRead:
    actor.require_permission("project_templates.manage")
    t = _load_template_in_family(db, template_id, actor.family_id)
    if t.is_builtin:
        raise HTTPException(status_code=400, detail="cannot edit built-in templates")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return TemplateRead.from_row(t)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> None:
    actor.require_permission("project_templates.manage")
    t = _load_template_in_family(db, template_id, actor.family_id)
    if t.is_builtin:
        raise HTTPException(status_code=400, detail="cannot delete built-in templates")
    db.delete(t)
    db.commit()


@router.get("/{template_id}/tasks", response_model=list[TemplateTaskRead])
def list_template_tasks(
    template_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[TemplateTaskRead]:
    actor.require_permission("project_templates.view")
    t = _load_template_in_family(db, template_id, actor.family_id)
    rows = (
        db.execute(
            select(ProjectTemplateTask)
            .where(ProjectTemplateTask.project_template_id == t.id)
            .order_by(ProjectTemplateTask.order_index, ProjectTemplateTask.created_at)
        )
        .scalars()
        .all()
    )
    return [TemplateTaskRead.from_row(r) for r in rows]


@router.post("/{template_id}/tasks", response_model=TemplateTaskRead, status_code=201)
def add_template_task(
    template_id: uuid.UUID,
    payload: TemplateTaskCreateIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> TemplateTaskRead:
    actor.require_permission("project_templates.manage")
    t = _load_template_in_family(db, template_id, actor.family_id)
    if t.is_builtin:
        raise HTTPException(status_code=400, detail="cannot edit built-in templates")
    tt = project_service.add_template_task(db, template_id=t.id, **payload.model_dump())
    db.commit()
    db.refresh(tt)
    return TemplateTaskRead.from_row(tt)
