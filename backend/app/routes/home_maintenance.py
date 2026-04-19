import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.home_maintenance import (
    HomeAsset,
    HomeZone,
    MaintenanceInstance,
    MaintenanceTemplate,
)

router = APIRouter(prefix="/families/{family_id}/home", tags=["home-maintenance"])


# ---------------------------------------------------------------------------
# Pydantic schemas (inline to keep the route file self-contained)
# ---------------------------------------------------------------------------

class ZoneCreate(BaseModel):
    name: str
    zone_type: str = "room"
    notes: str | None = None
    sort_order: int = 0

class ZoneRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    zone_type: str
    notes: str | None
    sort_order: int
    is_active: bool
    model_config = {"from_attributes": True}

class AssetCreate(BaseModel):
    name: str
    zone_id: uuid.UUID | None = None
    asset_type: str | None = None
    model: str | None = None
    serial: str | None = None
    notes: str | None = None

class AssetRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    zone_id: uuid.UUID | None
    name: str
    asset_type: str | None
    model: str | None
    serial: str | None
    notes: str | None
    is_active: bool
    model_config = {"from_attributes": True}

class TemplateCreate(BaseModel):
    name: str
    zone_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    description: str | None = None
    cadence_type: str = "monthly"
    rotation_month_mod: int | None = None
    included: list[str] = []
    not_included: list[str] = []
    done_means_done: str | None = None
    supplies: list[str] = []
    estimated_duration_minutes: int | None = None
    default_owner_member_id: uuid.UUID | None = None

class TemplateRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    zone_id: uuid.UUID | None
    asset_id: uuid.UUID | None
    name: str
    description: str | None
    cadence_type: str
    rotation_month_mod: int | None
    included: list
    not_included: list
    done_means_done: str | None
    supplies: list
    estimated_duration_minutes: int | None
    is_active: bool
    model_config = {"from_attributes": True}

class InstanceRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    template_id: uuid.UUID
    owner_member_id: uuid.UUID
    scheduled_for: datetime
    completed_at: datetime | None
    completed_by_member_id: uuid.UUID | None
    notes: str | None
    is_active: bool
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------

@router.get("/zones", response_model=list[ZoneRead])
def list_zones(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.view")
    return db.scalars(select(HomeZone).where(HomeZone.family_id == family_id, HomeZone.is_active == True).order_by(HomeZone.sort_order)).all()

@router.post("/zones", response_model=ZoneRead, status_code=201)
def create_zone(family_id: uuid.UUID, payload: ZoneCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.manage_zones")
    zone = HomeZone(family_id=family_id, **payload.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@router.get("/assets", response_model=list[AssetRead])
def list_assets(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.view")
    return db.scalars(select(HomeAsset).where(HomeAsset.family_id == family_id, HomeAsset.is_active == True)).all()

@router.post("/assets", response_model=AssetRead, status_code=201)
def create_asset(family_id: uuid.UUID, payload: AssetCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.manage_assets")
    asset = HomeAsset(family_id=family_id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.get("/templates", response_model=list[TemplateRead])
def list_templates(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.view")
    return db.scalars(select(MaintenanceTemplate).where(MaintenanceTemplate.family_id == family_id, MaintenanceTemplate.is_active == True)).all()

@router.post("/templates", response_model=TemplateRead, status_code=201)
def create_template(family_id: uuid.UUID, payload: TemplateCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.manage_templates")
    template = MaintenanceTemplate(family_id=family_id, **payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@router.get("/instances", response_model=list[InstanceRead])
def list_instances(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.view")
    return db.scalars(
        select(MaintenanceInstance)
        .where(MaintenanceInstance.family_id == family_id, MaintenanceInstance.is_active == True)
        .order_by(MaintenanceInstance.scheduled_for)
    ).all()

@router.post("/instances/{instance_id}/complete", response_model=InstanceRead)
def complete_instance(family_id: uuid.UUID, instance_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.complete_instance")
    instance = db.get(MaintenanceInstance, instance_id)
    if not instance or instance.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")
    instance.completed_at = datetime.now(timezone.utc)
    instance.completed_by_member_id = actor.member_id
    db.commit()
    db.refresh(instance)
    return instance

@router.post("/generate-upcoming", response_model=list[InstanceRead])
def generate_upcoming(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("home.manage_templates")
    templates = db.scalars(
        select(MaintenanceTemplate).where(MaintenanceTemplate.family_id == family_id, MaintenanceTemplate.is_active == True)
    ).all()
    now = datetime.now(timezone.utc)
    created = []
    for t in templates:
        if t.cadence_type == "on_demand":
            continue
        existing = db.scalars(
            select(MaintenanceInstance).where(
                MaintenanceInstance.template_id == t.id,
                MaintenanceInstance.scheduled_for >= now,
            )
        ).first()
        if existing:
            continue
        owner_id = t.default_owner_member_id or actor.member_id
        inst = MaintenanceInstance(
            family_id=family_id,
            template_id=t.id,
            owner_member_id=owner_id,
            scheduled_for=now,
        )
        db.add(inst)
        created.append(inst)
    db.commit()
    for inst in created:
        db.refresh(inst)
    return created
