import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import ChoreTemplate
from app.schemas.life_management import ChoreTemplateCreate
from app.services.tenant_guard import require_family


def list_chore_templates(db: Session, family_id: uuid.UUID) -> list[ChoreTemplate]:
    require_family(db, family_id)
    stmt = (
        select(ChoreTemplate)
        .where(ChoreTemplate.family_id == family_id)
        .where(ChoreTemplate.is_active.is_(True))
    )
    return list(db.scalars(stmt).all())


def get_chore_template(db: Session, family_id: uuid.UUID, template_id: uuid.UUID) -> ChoreTemplate:
    template = db.get(ChoreTemplate, template_id)
    if not template or template.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore template not found")
    return template


def create_chore_template(db: Session, family_id: uuid.UUID, payload: ChoreTemplateCreate) -> ChoreTemplate:
    require_family(db, family_id)
    template = ChoreTemplate(
        family_id=family_id,
        name=payload.name,
        description=payload.description,
        recurrence=payload.recurrence,
        due_time=payload.due_time,
        assignment_type=payload.assignment_type,
        assignment_rule=payload.assignment_rule,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def resolve_assignees(template: ChoreTemplate, day_of_month: int) -> list[uuid.UUID]:
    """Evaluate assignment_rule for a given day and return assigned member UUIDs."""
    rule = template.assignment_rule
    if template.assignment_type == "fixed":
        assigned_to = rule.get("assigned_to")
        return [uuid.UUID(assigned_to)] if assigned_to else []

    if template.assignment_type == "rotating_daily":
        is_odd = day_of_month % 2 == 1
        key = "odd" if is_odd else "even"
        member_id = rule.get(key)
        return [uuid.UUID(member_id)] if member_id else []

    if template.assignment_type == "rotating_weekly":
        owner = rule.get("current_owner")
        return [uuid.UUID(owner)] if owner else []

    return []
