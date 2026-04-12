import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.life_management import ChoreTemplateCreate, ChoreTemplateRead
from app.services import chore_service

router = APIRouter(prefix="/families/{family_id}/chore-templates", tags=["chores"])


@router.get("", response_model=list[ChoreTemplateRead])
def list_chore_templates(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return chore_service.list_chore_templates(db, family_id)


@router.post("", response_model=ChoreTemplateRead, status_code=201)
def create_chore_template(family_id: uuid.UUID, payload: ChoreTemplateCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return chore_service.create_chore_template(db, family_id, payload)


@router.get("/{template_id}", response_model=ChoreTemplateRead)
def get_chore_template(family_id: uuid.UUID, template_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return chore_service.get_chore_template(db, family_id, template_id)
