"""Backend coverage for Sprint Expansion Phase 1 — push notifications.

Covers:

- device registration + revoke round-trip
- send_push happy path: provider_accepted rows carry a ticket id
- poll_pending_receipts moves rows to provider_handoff_ok or
  provider_error, deactivates devices on DeviceNotRegistered
- permission denial: a child-tier actor cannot call
  push.send_to_member or the family-wide delivery log
- AI tool: push-delivered path skips Action Inbox; no-device path
  creates a ParentActionItem fallback
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.foundation import (
    Family,
    FamilyMember,
    Session as SessionModel,
    UserAccount,
)
from app.models.push import PushDelivery, PushDevice
from app.services import push_service
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Test client + bearer token helpers
# ---------------------------------------------------------------------------


def _make_account_and_token(db: Session, member_id, email: str) -> str:
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
# Unit tests against push_service directly (no HTTP layer)
# ---------------------------------------------------------------------------


class TestPushServiceSend:
    """push_service.send_push end-to-end, with Expo monkey-patched."""

    def test_accepted_ticket_writes_provider_accepted_row(self, db, family, adults, monkeypatch):
        robert = adults["robert"]
        push_service.register_device(
            db,
            family_member_id=robert.id,
            expo_push_token="ExponentPushToken[abc]",
            platform="ios",
            device_label="Robert's iPhone",
        )
        db.commit()

        captured: dict[str, Any] = {}

        def fake_send(messages):
            captured["messages"] = messages
            return {"data": [{"status": "ok", "id": "expo-ticket-1"}]}

        monkeypatch.setattr(push_service, "_expo_send", fake_send)

        result = push_service.send_push(
            db,
            family_member_id=robert.id,
            category="test",
            title="hello",
            body="world",
            trigger_source="unit.test",
        )
        db.commit()

        assert result.accepted_count == 1
        assert result.error_count == 0
        rows = db.execute(
            select(PushDelivery).where(PushDelivery.family_member_id == robert.id)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "provider_accepted"
        assert rows[0].provider_ticket_id == "expo-ticket-1"
        assert captured["messages"][0]["to"] == "ExponentPushToken[abc]"

    def test_no_active_devices_returns_empty_result(self, db, family, adults):
        result = push_service.send_push(
            db,
            family_member_id=adults["robert"].id,
            category="test",
            title="x",
            body="y",
            trigger_source="unit.test",
        )
        assert result.accepted_count == 0
        assert result.error_count == 0
        assert result.delivery_ids == []

    def test_expo_request_failure_marks_row_provider_error(self, db, adults, monkeypatch):
        robert = adults["robert"]
        push_service.register_device(
            db,
            family_member_id=robert.id,
            expo_push_token="ExponentPushToken[err]",
            platform="ios",
        )
        db.commit()

        def blowup(messages):
            raise RuntimeError("expo is on fire")

        monkeypatch.setattr(push_service, "_expo_send", blowup)
        result = push_service.send_push(
            db,
            family_member_id=robert.id,
            category="t", title="x", body="y",
            trigger_source="unit.test",
        )
        db.commit()

        assert result.accepted_count == 0
        assert result.error_count == 1
        row = db.execute(select(PushDelivery)).scalars().one()
        assert row.status == "provider_error"
        assert "expo is on fire" in (row.error_message or "")

    def test_device_not_registered_ticket_deactivates_device(self, db, adults, monkeypatch):
        robert = adults["robert"]
        device = push_service.register_device(
            db,
            family_member_id=robert.id,
            expo_push_token="ExponentPushToken[stale]",
            platform="ios",
        )
        db.commit()

        def fake_send(messages):
            return {"data": [{
                "status": "error",
                "message": "token is not registered",
                "details": {"error": "DeviceNotRegistered"},
            }]}

        monkeypatch.setattr(push_service, "_expo_send", fake_send)
        push_service.send_push(
            db,
            family_member_id=robert.id,
            category="t", title="x", body="y",
            trigger_source="unit.test",
        )
        db.commit()
        db.refresh(device)
        assert device.is_active is False


class TestReceiptPolling:
    def test_accepted_ticket_becomes_handoff_ok(self, db, adults, monkeypatch):
        robert = adults["robert"]
        push_service.register_device(
            db, family_member_id=robert.id,
            expo_push_token="ExponentPushToken[r1]", platform="ios",
        )
        monkeypatch.setattr(
            push_service, "_expo_send",
            lambda msgs: {"data": [{"status": "ok", "id": "ticket-abc"}]},
        )
        push_service.send_push(
            db, family_member_id=robert.id,
            category="t", title="x", body="y",
            trigger_source="unit.test",
        )
        db.commit()

        monkeypatch.setattr(
            push_service, "_expo_get_receipts",
            lambda ids: {"data": {"ticket-abc": {"status": "ok"}}},
        )
        stats = push_service.poll_pending_receipts(db)
        db.commit()

        assert stats["checked"] == 1
        assert stats["handoff_ok"] == 1
        row = db.execute(select(PushDelivery)).scalars().one()
        assert row.status == "provider_handoff_ok"
        assert row.provider_handoff_at is not None

    def test_receipt_error_with_device_not_registered_deactivates(self, db, adults, monkeypatch):
        robert = adults["robert"]
        device = push_service.register_device(
            db, family_member_id=robert.id,
            expo_push_token="ExponentPushToken[r2]", platform="ios",
        )
        monkeypatch.setattr(
            push_service, "_expo_send",
            lambda msgs: {"data": [{"status": "ok", "id": "ticket-xyz"}]},
        )
        push_service.send_push(
            db, family_member_id=robert.id,
            category="t", title="x", body="y",
            trigger_source="unit.test",
        )
        db.commit()

        monkeypatch.setattr(
            push_service, "_expo_get_receipts",
            lambda ids: {"data": {"ticket-xyz": {
                "status": "error",
                "message": "stale",
                "details": {"error": "DeviceNotRegistered"},
            }}},
        )
        stats = push_service.poll_pending_receipts(db)
        db.commit()

        assert stats["errored"] == 1
        assert stats["deactivated"] == 1
        db.refresh(device)
        assert device.is_active is False


# ---------------------------------------------------------------------------
# HTTP route coverage (happy-path + permission denial)
# ---------------------------------------------------------------------------


class TestPushRoutes:
    def test_register_and_list_and_revoke_device(self, client, db, family, adults):
        robert = adults["robert"]
        tok = _make_account_and_token(db, robert.id, "robert-push@scout.local")
        headers = {"Authorization": f"Bearer {tok}"}

        r = client.post(
            "/api/push/devices",
            headers=headers,
            json={
                "expo_push_token": "ExponentPushToken[route-1]",
                "platform": "ios",
                "device_label": "Robert's iPhone",
            },
        )
        assert r.status_code == 201
        device_id = r.json()["id"]

        r = client.get("/api/push/devices/me", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1

        r = client.delete(f"/api/push/devices/{device_id}", headers=headers)
        assert r.status_code == 204

        device = db.get(PushDevice, uuid.UUID(device_id))
        assert device.is_active is False

    def test_child_cannot_test_send(self, client, db, family, adults, children, monkeypatch):
        # Child tries to push-test Robert — should 403 on permission check.
        sadie = children["sadie"]
        tok = _make_account_and_token(db, sadie.id, "sadie-push@scout.local")
        monkeypatch.setattr(
            push_service, "_expo_send",
            lambda msgs: {"data": [{"status": "ok", "id": "x"}]},
        )
        r = client.post(
            "/api/push/test-send",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "target_family_member_id": str(adults["robert"].id),
                "title": "hi",
                "body": "from sadie",
            },
        )
        assert r.status_code == 403
        assert "push.send_to_member" in r.json().get("detail", "")

    def test_child_cannot_view_family_delivery_log(self, client, db, children):
        sadie = children["sadie"]
        tok = _make_account_and_token(db, sadie.id, "sadie-log@scout.local")
        r = client.get(
            "/api/push/deliveries",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 403

    def test_adult_test_send_creates_delivery_rows(self, client, db, family, adults, monkeypatch):
        robert = adults["robert"]
        megan = adults["megan"]
        push_service.register_device(
            db, family_member_id=megan.id,
            expo_push_token="ExponentPushToken[megan-1]", platform="ios",
        )
        db.commit()

        monkeypatch.setattr(
            push_service, "_expo_send",
            lambda msgs: {"data": [{"status": "ok", "id": "t-adult"}]},
        )

        tok = _make_account_and_token(db, robert.id, "robert-send@scout.local")
        r = client.post(
            "/api/push/test-send",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "target_family_member_id": str(megan.id),
                "title": "hi megan",
                "body": "from robert",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["accepted_count"] == 1
        assert body["error_count"] == 0

        rows = db.execute(
            select(PushDelivery).where(PushDelivery.family_member_id == megan.id)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "provider_accepted"


# ---------------------------------------------------------------------------
# AI tool integration — push primary, inbox fallback
# ---------------------------------------------------------------------------


class TestAIToolIntegration:
    def _executor(self, db, family, member):
        from app.ai.tools import ToolExecutor
        return ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=member.id,
            actor_role="adult",
            surface="chat",
            allowed_tools=["send_notification_or_create_action"],
        )

    def test_push_delivered_path_skips_action_inbox(self, db, family, adults, monkeypatch):
        from app.ai.tools import _send_notification_or_create_action

        robert = adults["robert"]
        megan = adults["megan"]
        push_service.register_device(
            db, family_member_id=megan.id,
            expo_push_token="ExponentPushToken[ai-1]", platform="ios",
        )
        db.commit()

        monkeypatch.setattr(
            push_service, "_expo_send",
            lambda msgs: {"data": [{"status": "ok", "id": "ai-ticket"}]},
        )

        result = _send_notification_or_create_action(
            self._executor(db, family, robert),
            {
                "target_member_id": str(megan.id),
                "message": "remember to water the plants",
                "confirmed": True,
            },
        )
        db.commit()

        assert result["status"] == "push_delivered"
        assert result["accepted_count"] == 1

        inbox_rows = db.execute(
            select(ParentActionItem).where(ParentActionItem.family_id == family.id)
        ).scalars().all()
        assert inbox_rows == []

    def test_no_device_falls_back_to_action_inbox(self, db, family, adults):
        from app.ai.tools import _send_notification_or_create_action

        robert = adults["robert"]
        megan = adults["megan"]

        result = _send_notification_or_create_action(
            self._executor(db, family, robert),
            {
                "target_member_id": str(megan.id),
                "message": "no push available, should go to inbox",
                "confirmed": True,
            },
        )
        db.commit()

        assert result["status"] == "fallback_action_inbox"
        assert "action_item_id" in result

        inbox_rows = db.execute(
            select(ParentActionItem).where(ParentActionItem.family_id == family.id)
        ).scalars().all()
        assert len(inbox_rows) == 1
        assert inbox_rows[0].detail == "no push available, should go to inbox"

    def test_invalid_target_returns_error(self, db, family, adults):
        from app.ai.tools import _send_notification_or_create_action

        result = _send_notification_or_create_action(
            self._executor(db, family, adults["robert"]),
            {
                "target_member_id": str(uuid.uuid4()),  # not in family
                "message": "ghost",
                "confirmed": True,
            },
        )
        assert "error" in result
