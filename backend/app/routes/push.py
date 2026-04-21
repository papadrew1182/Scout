"""Push notification routes.

Self-scoped device lifecycle lives at `/api/push/devices*`; self-scoped
delivery log at `/api/push/deliveries/me`. Family-wide log and test-send
require `push.view_delivery_log` and `push.send_to_member` respectively.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import FamilyMember
from app.models.push import PushDelivery, PushDevice
from app.services import push_service

router = APIRouter(prefix="/api/push", tags=["push"])


class DeviceRegisterIn(BaseModel):
    expo_push_token: str = Field(min_length=1, max_length=500)
    platform: Literal["ios", "android", "web"]
    device_label: str | None = Field(default=None, max_length=200)
    app_version: str | None = Field(default=None, max_length=50)


class DeviceRead(BaseModel):
    id: uuid.UUID
    family_member_id: uuid.UUID
    device_label: str | None
    platform: str
    app_version: str | None
    is_active: bool
    last_registered_at: datetime
    last_successful_delivery_at: datetime | None

    @classmethod
    def from_row(cls, row: PushDevice) -> "DeviceRead":
        return cls(
            id=row.id,
            family_member_id=row.family_member_id,
            device_label=row.device_label,
            platform=row.platform,
            app_version=row.app_version,
            is_active=row.is_active,
            last_registered_at=row.last_registered_at,
            last_successful_delivery_at=row.last_successful_delivery_at,
        )


class DeliveryRead(BaseModel):
    id: uuid.UUID
    notification_group_id: uuid.UUID
    family_member_id: uuid.UUID
    push_device_id: uuid.UUID
    category: str
    title: str
    body: str
    data: dict[str, Any]
    trigger_source: str
    status: str
    provider_ticket_id: str | None
    error_message: str | None
    sent_at: datetime | None
    provider_handoff_at: datetime | None
    tapped_at: datetime | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: PushDelivery) -> "DeliveryRead":
        return cls(
            id=row.id,
            notification_group_id=row.notification_group_id,
            family_member_id=row.family_member_id,
            push_device_id=row.push_device_id,
            category=row.category,
            title=row.title,
            body=row.body,
            data=row.data or {},
            trigger_source=row.trigger_source,
            status=row.status,
            provider_ticket_id=row.provider_ticket_id,
            error_message=row.error_message,
            sent_at=row.sent_at,
            provider_handoff_at=row.provider_handoff_at,
            tapped_at=row.tapped_at,
            created_at=row.created_at,
        )


class TestSendIn(BaseModel):
    target_family_member_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=500)
    category: str = Field(default="test", max_length=50)
    data: dict[str, Any] | None = None


class SendResultOut(BaseModel):
    notification_group_id: uuid.UUID
    delivery_ids: list[uuid.UUID]
    accepted_count: int
    error_count: int


@router.post("/devices", response_model=DeviceRead, status_code=201)
def register_device(
    payload: DeviceRegisterIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> DeviceRead:
    actor.require_permission("push.register_device")
    device = push_service.register_device(
        db,
        family_member_id=actor.member_id,
        expo_push_token=payload.expo_push_token,
        platform=payload.platform,
        device_label=payload.device_label,
        app_version=payload.app_version,
    )
    db.commit()
    db.refresh(device)
    return DeviceRead.from_row(device)


@router.get("/devices/me", response_model=list[DeviceRead])
def list_my_devices(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[DeviceRead]:
    rows = (
        db.execute(
            select(PushDevice)
            .where(PushDevice.family_member_id == actor.member_id)
            .order_by(PushDevice.last_registered_at.desc())
        )
        .scalars()
        .all()
    )
    return [DeviceRead.from_row(r) for r in rows]


@router.delete("/devices/{device_id}", status_code=204)
def revoke_device(
    device_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> None:
    actor.require_permission("push.revoke_device")
    ok = push_service.revoke_device(db, device_id=device_id, family_member_id=actor.member_id)
    if not ok:
        raise HTTPException(status_code=404, detail="device not found")
    db.commit()


@router.get("/deliveries/me", response_model=list[DeliveryRead])
def list_my_deliveries(
    limit: int = 50,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[DeliveryRead]:
    limit = max(1, min(limit, 200))
    rows = (
        db.execute(
            select(PushDelivery)
            .where(PushDelivery.family_member_id == actor.member_id)
            .order_by(PushDelivery.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [DeliveryRead.from_row(r) for r in rows]


@router.get("/deliveries", response_model=list[DeliveryRead])
def list_family_deliveries(
    limit: int = 50,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[DeliveryRead]:
    actor.require_permission("push.view_delivery_log")
    limit = max(1, min(limit, 500))
    # Restrict to deliveries for members of the caller's family.
    rows = (
        db.execute(
            select(PushDelivery)
            .join(FamilyMember, FamilyMember.id == PushDelivery.family_member_id)
            .where(FamilyMember.family_id == actor.family_id)
            .order_by(PushDelivery.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [DeliveryRead.from_row(r) for r in rows]


@router.post("/deliveries/{delivery_id}/tap", status_code=204)
def record_tap(
    delivery_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> None:
    # Self-scoped: the service rejects a tap on another member's
    # delivery. Gate on push.register_device as the floor tier —
    # if a user cannot hold a device, they have no tap to record.
    actor.require_permission("push.register_device")
    ok = push_service.record_tap_event(
        db, delivery_id=delivery_id, family_member_id=actor.member_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="delivery not found")
    db.commit()


@router.post("/test-send", response_model=SendResultOut)
def test_send(
    payload: TestSendIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> SendResultOut:
    actor.require_permission("push.send_to_member")
    # Prevent cross-family sends.
    target = db.get(FamilyMember, payload.target_family_member_id)
    if target is None or target.family_id != actor.family_id:
        raise HTTPException(status_code=404, detail="target member not found in your family")

    result = push_service.send_push(
        db,
        family_member_id=target.id,
        category=payload.category,
        title=payload.title,
        body=payload.body,
        data=payload.data,
        trigger_source="push.test_send",
    )
    db.commit()
    return SendResultOut(
        notification_group_id=result.notification_group_id,
        delivery_ids=result.delivery_ids,
        accepted_count=result.accepted_count,
        error_count=result.error_count,
    )
