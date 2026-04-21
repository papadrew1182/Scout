"""Push notification service for Phase 1.

Provider acceptance and provider handoff are different states. Sending a
message returns a *ticket* which means Expo accepted the payload; the
ticket must be polled later to get a *receipt* which means Expo handed
the payload to APNs or FCM. Neither guarantees device display.

Delivery rows transition:

    queued
      ├─ send_push → provider_accepted (ticket stored)
      ├─ send_push → provider_error (immediate rejection)
      └─ poll_pending_receipts → provider_handoff_ok
                               └─ provider_error
                                 └─ on DeviceNotRegistered → deactivate device
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import push_settings
from app.models.push import PushDelivery, PushDevice

logger = logging.getLogger("scout.push")

_EXPO_SEND_PATH = "/send"
_EXPO_RECEIPTS_PATH = "/getReceipts"
# Expo batches receipt fetches at 1000 ids per call.
_EXPO_RECEIPT_CHUNK = 1000


@dataclass
class SendResult:
    notification_group_id: uuid.UUID
    delivery_ids: list[uuid.UUID]
    accepted_count: int
    error_count: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expo_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/json",
    }
    if push_settings.expo_push_security_enabled and push_settings.expo_access_token:
        headers["Authorization"] = f"Bearer {push_settings.expo_access_token}"
    return headers


def _expo_send(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """POST to Expo's push send endpoint. Monkeypatch in tests."""
    url = push_settings.expo_push_api_base + _EXPO_SEND_PATH
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=_expo_headers(), json=messages)
        r.raise_for_status()
        return r.json()


def _expo_get_receipts(ticket_ids: list[str]) -> dict[str, Any]:
    """POST to Expo's getReceipts endpoint. Monkeypatch in tests."""
    url = push_settings.expo_push_api_base + _EXPO_RECEIPTS_PATH
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=_expo_headers(), json={"ids": ticket_ids})
        r.raise_for_status()
        return r.json()


def register_device(
    db: Session,
    *,
    family_member_id: uuid.UUID,
    expo_push_token: str,
    platform: str,
    device_label: str | None = None,
    app_version: str | None = None,
) -> PushDevice:
    """Register or re-activate a device.

    Expo tokens are globally unique so we upsert by token. A token that
    re-appears for the same member is re-activated; a token that re-appears
    for a different member is transferred (a phone sold between members,
    for example).
    """
    existing = db.execute(
        select(PushDevice).where(PushDevice.expo_push_token == expo_push_token)
    ).scalar_one_or_none()

    now = _utcnow()
    if existing is not None:
        existing.family_member_id = family_member_id
        existing.platform = platform
        existing.device_label = device_label
        existing.app_version = app_version
        existing.is_active = True
        existing.last_registered_at = now
        existing.updated_at = now
        db.flush()
        return existing

    device = PushDevice(
        family_member_id=family_member_id,
        expo_push_token=expo_push_token,
        device_label=device_label,
        platform=platform,
        app_version=app_version,
        is_active=True,
        last_registered_at=now,
    )
    db.add(device)
    db.flush()
    return device


def revoke_device(db: Session, *, device_id: uuid.UUID, family_member_id: uuid.UUID) -> bool:
    """Soft-delete (is_active=false) a device the caller owns.

    Returns True if a row was updated, False if none matched.
    """
    device = db.execute(
        select(PushDevice).where(
            PushDevice.id == device_id,
            PushDevice.family_member_id == family_member_id,
        )
    ).scalar_one_or_none()
    if device is None:
        return False
    device.is_active = False
    device.updated_at = _utcnow()
    db.flush()
    return True


def deactivate_unregistered_device(db: Session, *, expo_push_token: str) -> None:
    """Deactivate a device whose token Expo reports as DeviceNotRegistered."""
    device = db.execute(
        select(PushDevice).where(PushDevice.expo_push_token == expo_push_token)
    ).scalar_one_or_none()
    if device is None or not device.is_active:
        return
    device.is_active = False
    device.updated_at = _utcnow()
    db.flush()


def send_push(
    db: Session,
    *,
    family_member_id: uuid.UUID,
    category: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    trigger_source: str,
) -> SendResult:
    """Send a push to every active device for a member.

    One delivery row is written per device attempt. The shared
    `notification_group_id` lets downstream callers (AI tool, tap
    handler) correlate attempts to a logical notification.

    Provider acceptance is set only after Expo returns `status=ok`.
    Per-message errors move the row to `provider_error` immediately.
    Receipt polling later moves `provider_accepted` rows to
    `provider_handoff_ok` or `provider_error`.
    """
    data = data or {}
    group_id = uuid.uuid4()

    devices = (
        db.execute(
            select(PushDevice).where(
                PushDevice.family_member_id == family_member_id,
                PushDevice.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )

    if not devices:
        return SendResult(notification_group_id=group_id, delivery_ids=[], accepted_count=0, error_count=0)

    # Build one row per device first so we have IDs to report back.
    deliveries: list[PushDelivery] = []
    for device in devices:
        row = PushDelivery(
            notification_group_id=group_id,
            family_member_id=family_member_id,
            push_device_id=device.id,
            provider="expo",
            category=category,
            title=title,
            body=body,
            data=data,
            trigger_source=trigger_source,
            status="queued",
        )
        db.add(row)
        deliveries.append(row)
    db.flush()

    # Build Expo payload in the same order. `category` is tracked only
    # on the delivery row (trigger_source / category columns); Expo's
    # push-send schema doesn't recognize a top-level category field, so
    # we don't emit one here — prior `_category` key was silently
    # stripped by Expo and added nothing.
    messages = [
        {
            "to": device.expo_push_token,
            "title": title,
            "body": body,
            "sound": "default",
            "data": {**data, "scout_delivery_id": str(row.id)},
        }
        for device, row in zip(devices, deliveries)
    ]

    now = _utcnow()
    accepted = 0
    errored = 0
    try:
        response = _expo_send(messages)
    except Exception as exc:
        logger.warning("expo_send_failed: %s", str(exc)[:200])
        for row in deliveries:
            row.status = "provider_error"
            row.error_message = f"expo_send_failed: {str(exc)[:200]}"
            row.sent_at = now
            row.updated_at = now
            errored += 1
        db.flush()
        return SendResult(
            notification_group_id=group_id,
            delivery_ids=[r.id for r in deliveries],
            accepted_count=0,
            error_count=errored,
        )

    tickets = response.get("data") or []
    for row, ticket in zip(deliveries, tickets):
        row.sent_at = now
        row.updated_at = now
        if isinstance(ticket, dict) and ticket.get("status") == "ok":
            row.status = "provider_accepted"
            row.provider_ticket_id = ticket.get("id")
            accepted += 1
        else:
            row.status = "provider_error"
            msg = ""
            if isinstance(ticket, dict):
                msg = ticket.get("message") or ""
                details = ticket.get("details") or {}
                if details.get("error") == "DeviceNotRegistered":
                    deactivate_unregistered_device(
                        db, expo_push_token=messages[deliveries.index(row)]["to"]
                    )
            row.error_message = msg[:500] if msg else "expo returned non-ok ticket"
            errored += 1

    # Short tickets list (request-level error) leaves extra rows queued;
    # mark them as errors so they don't sit forever.
    for row in deliveries[len(tickets):]:
        row.status = "provider_error"
        row.error_message = "expo response missing ticket for this row"
        row.sent_at = now
        row.updated_at = now
        errored += 1

    db.flush()
    return SendResult(
        notification_group_id=group_id,
        delivery_ids=[r.id for r in deliveries],
        accepted_count=accepted,
        error_count=errored,
    )


def send_bulk_push(
    db: Session,
    *,
    targets: Iterable[uuid.UUID],
    category: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    trigger_source: str,
) -> list[SendResult]:
    """Send the same notification to multiple members."""
    return [
        send_push(
            db,
            family_member_id=member_id,
            category=category,
            title=title,
            body=body,
            data=data,
            trigger_source=trigger_source,
        )
        for member_id in targets
    ]


def poll_pending_receipts(db: Session, *, limit: int = 1000) -> dict[str, int]:
    """Fetch Expo receipts for pending tickets and advance row status."""
    pending = (
        db.execute(
            select(PushDelivery)
            .where(
                PushDelivery.status == "provider_accepted",
                PushDelivery.provider_ticket_id.is_not(None),
            )
            .order_by(PushDelivery.created_at)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    if not pending:
        return {"checked": 0, "handoff_ok": 0, "errored": 0, "deactivated": 0}

    by_ticket = {row.provider_ticket_id: row for row in pending if row.provider_ticket_id}
    ticket_ids = list(by_ticket.keys())

    handoff_ok = 0
    errored = 0
    deactivated = 0
    now = _utcnow()

    for i in range(0, len(ticket_ids), _EXPO_RECEIPT_CHUNK):
        chunk = ticket_ids[i : i + _EXPO_RECEIPT_CHUNK]
        try:
            response = _expo_get_receipts(chunk)
        except Exception as exc:
            logger.warning("expo_receipts_failed: %s", str(exc)[:200])
            continue

        receipts = response.get("data") or {}
        for ticket_id in chunk:
            row = by_ticket[ticket_id]
            receipt = receipts.get(ticket_id)
            row.receipt_checked_at = now
            row.updated_at = now
            if receipt is None:
                # Expo hasn't produced a receipt yet; leave in
                # provider_accepted and try again next tick.
                continue
            row.provider_receipt_payload = receipt
            status = receipt.get("status") if isinstance(receipt, dict) else None
            if status == "ok":
                row.status = "provider_handoff_ok"
                row.provider_receipt_status = "ok"
                row.provider_handoff_at = now
                _mark_device_delivered(db, row.push_device_id, now)
                handoff_ok += 1
            else:
                row.status = "provider_error"
                row.provider_receipt_status = status or "unknown"
                msg = receipt.get("message") if isinstance(receipt, dict) else None
                row.error_message = (msg or "expo receipt not ok")[:500]
                details = receipt.get("details") if isinstance(receipt, dict) else None
                if isinstance(details, dict) and details.get("error") == "DeviceNotRegistered":
                    device = db.get(PushDevice, row.push_device_id)
                    if device and device.is_active:
                        device.is_active = False
                        device.updated_at = now
                        deactivated += 1
                errored += 1

    db.flush()
    return {
        "checked": len(ticket_ids),
        "handoff_ok": handoff_ok,
        "errored": errored,
        "deactivated": deactivated,
    }


def _mark_device_delivered(db: Session, device_id: uuid.UUID, now: datetime) -> None:
    device = db.get(PushDevice, device_id)
    if device is not None:
        device.last_successful_delivery_at = now
        device.updated_at = now


def record_tap_event(
    db: Session, *, delivery_id: uuid.UUID, family_member_id: uuid.UUID
) -> bool:
    """Mark a delivery as tapped by the current member.

    Ownership-checked: a delivery can only be tapped by the member it was
    sent to. Returns True if a row was updated.
    """
    row = db.execute(
        select(PushDelivery).where(
            PushDelivery.id == delivery_id,
            PushDelivery.family_member_id == family_member_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    if row.tapped_at is None:
        row.tapped_at = _utcnow()
        row.updated_at = row.tapped_at
        db.flush()
    return True


# Scheduler entry point — wired from app.scheduler. Named with a verb
# so the ergonomics match run_morning_brief_tick et al.
def run_push_receipt_poll_tick(db: Session, *, now_utc: datetime | None = None) -> dict[str, int]:
    """Scheduler-friendly wrapper around poll_pending_receipts."""
    return poll_pending_receipts(db, limit=push_settings.push_receipt_poll_batch)
