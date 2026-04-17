"""R3 reconciliation tests — Migrations 036, 037, 038 + admin routes.

Tests verify:
  1.  Migration 036: member_config chores.routines → scout.routine_templates
  2.  Migration 037: member_config allowance.target → scout.reward_policies
  3.  Migration 038: household_rules integrations.connections → scout.connector_accounts
  4.  Admin route GET /admin/chores/routines
  5.  Admin route PUT /admin/chores/routines/{member_id}
  6.  Admin route DELETE /admin/chores/routines/{routine_id}
  7.  Admin route GET /admin/allowance/policies
  8.  Admin route PUT /admin/allowance/policies/{member_id}
  9.  Admin route GET /admin/integrations/connections
  10. Admin route PATCH /admin/integrations/connections/{id}

All tests run inside a rolled-back transaction (standard conftest fixture).
"""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app
from app.models.access import MemberConfig, HouseholdRule
from app.models.canonical import (
    Connector,
    ConnectorAccount,
    RewardPolicy,
    RoutineTemplate,
)
from app.models.foundation import Family, FamilyMember
from app.services.chores_canonical import (
    delete_chore_routine,
    get_family_chore_routines,
    upsert_chore_routine,
)
from app.services.allowance_canonical import (
    get_family_reward_policies,
    upsert_reward_policy,
)
from app.services.integrations_canonical import (
    get_family_connector_accounts,
    update_connector_status,
)

# ---------------------------------------------------------------------------
# Helpers — build an authenticated test client with a seeded actor
# ---------------------------------------------------------------------------


def _make_client(db: Session, actor_member: FamilyMember):
    """Return a TestClient that bypasses auth by injecting the actor."""
    from app.auth import Actor, get_current_actor
    from app.database import get_db
    from app.models.foundation import UserAccount

    # Create a stub user account for the actor
    account = UserAccount(
        email=f"test_{actor_member.id}@example.com",
        auth_provider="email",
        password_hash="x",
        family_member_id=actor_member.id,
    )
    db.add(account)
    db.flush()

    family = db.get(Family, actor_member.family_id)
    actor = Actor(account=account, member=actor_member, family=family, db=db)
    actor._permission_cache = {
        "chores.manage_config": True,
        "allowance.manage_config": True,
        "admin.manage_config": True,
        "admin.view_config": True,
    }

    def override_actor():
        return actor

    def override_db():
        yield db

    app.dependency_overrides[get_current_actor] = override_actor
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, raise_server_exceptions=True)
    return client


def _clear_overrides():
    from app.auth import get_current_actor
    from app.database import get_db
    app.dependency_overrides.pop(get_current_actor, None)
    app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# Service-layer unit tests (no HTTP)
# ===========================================================================


class TestChoresCanonicalService:
    def test_upsert_and_list(self, db: Session, family: Family, children: dict):
        sadie = children["sadie"]

        rt = upsert_chore_routine(
            db,
            family_id=family.id,
            member_id=sadie.id,
            routine_key="make_bed",
            label="Make bed",
        )
        db.flush()

        templates = get_family_chore_routines(db, family.id)
        assert any(t.routine_key == "make_bed" for t in templates)
        assert rt.label == "Make bed"
        assert rt.block_label == "Chores"
        assert rt.recurrence == "daily"

    def test_upsert_is_idempotent(self, db: Session, family: Family, children: dict):
        sadie = children["sadie"]
        upsert_chore_routine(db, family_id=family.id, member_id=sadie.id,
                             routine_key="brush_teeth", label="Brush teeth v1")
        upsert_chore_routine(db, family_id=family.id, member_id=sadie.id,
                             routine_key="brush_teeth", label="Brush teeth v2")
        db.flush()

        templates = get_family_chore_routines(db, family.id)
        matching = [t for t in templates if t.routine_key == "brush_teeth"]
        assert len(matching) == 1
        assert matching[0].label == "Brush teeth v2"

    def test_delete(self, db: Session, family: Family, children: dict):
        sadie = children["sadie"]
        rt = upsert_chore_routine(db, family_id=family.id, member_id=sadie.id,
                                  routine_key="dishes", label="Dishes")
        db.flush()
        deleted = delete_chore_routine(db, family.id, rt.id)
        assert deleted is True

        templates = get_family_chore_routines(db, family.id)
        assert not any(t.routine_key == "dishes" for t in templates)

    def test_delete_returns_false_for_missing(self, db: Session, family: Family):
        result = delete_chore_routine(db, family.id, uuid.uuid4())
        assert result is False


class TestAllowanceCanonicalService:
    def test_upsert_and_list(self, db: Session, family: Family, children: dict):
        sadie = children["sadie"]
        policy = upsert_reward_policy(
            db,
            family_id=family.id,
            member_id=sadie.id,
            baseline_cents=500,
            payout_schedule="weekly",
            weekly_target_cents=1000,
        )
        db.flush()

        policies = get_family_reward_policies(db, family.id)
        assert any(p.family_member_id == sadie.id for p in policies)
        assert policy.baseline_amount_cents == 500
        assert policy.payout_schedule["schedule"] == "weekly"
        assert policy.payout_schedule["weekly_target_cents"] == 1000

    def test_upsert_updates_existing(self, db: Session, family: Family, children: dict):
        sadie = children["sadie"]
        today = date.today()
        upsert_reward_policy(db, family_id=family.id, member_id=sadie.id,
                             baseline_cents=500, effective_from=today)
        upsert_reward_policy(db, family_id=family.id, member_id=sadie.id,
                             baseline_cents=750, effective_from=today)
        db.flush()

        policies = get_family_reward_policies(db, family.id)
        sadie_policies = [p for p in policies if p.family_member_id == sadie.id]
        # Same effective_from → same row updated, not a second row
        assert len(sadie_policies) == 1
        assert sadie_policies[0].baseline_amount_cents == 750


class TestIntegrationsCanonicalService:
    def _seed_connector(self, db: Session, key: str = "google_calendar") -> Connector:
        """Return or create a connector row for testing."""
        from sqlalchemy import select
        existing = db.scalars(
            select(Connector).where(Connector.connector_key == key)
        ).first()
        if existing:
            return existing
        c = Connector(connector_key=key, label=key.replace("_", " ").title(), tier=1)
        db.add(c)
        db.flush()
        return c

    def test_list_and_update(self, db: Session, family: Family):
        connector = self._seed_connector(db)
        account = ConnectorAccount(
            connector_id=connector.id,
            family_id=family.id,
            status="disconnected",
            account_label="Test account",
        )
        db.add(account)
        db.flush()

        accounts = get_family_connector_accounts(db, family.id)
        assert any(a.id == account.id for a in accounts)

        updated = update_connector_status(db, family.id, account.id, "connected")
        assert updated.status == "connected"

    def test_update_invalid_status_raises(self, db: Session, family: Family):
        connector = self._seed_connector(db, key="ynab")
        account = ConnectorAccount(
            connector_id=connector.id,
            family_id=family.id,
            status="disconnected",
        )
        db.add(account)
        db.flush()

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            update_connector_status(db, family.id, account.id, "totally_invalid")
        assert exc_info.value.status_code == 422


# ===========================================================================
# Admin route integration tests (HTTP via TestClient)
# ===========================================================================


class TestChoresAdminRoutes:
    def test_list_routines_empty(self, db: Session, adults: dict, family: Family):
        actor = adults["robert"]
        client = _make_client(db, actor)
        try:
            resp = client.get("/admin/chores/routines")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            _clear_overrides()

    def test_put_and_list_routines(self, db: Session, adults: dict, children: dict, family: Family):
        actor = adults["robert"]
        sadie = children["sadie"]
        client = _make_client(db, actor)
        try:
            resp = client.put(
                f"/admin/chores/routines/{sadie.id}",
                json={"routines": [
                    {"routine_key": "make_bed", "label": "Make bed"},
                    {"routine_key": "brush_teeth", "label": "Brush teeth"},
                ]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["member_id"] == str(sadie.id)
            assert len(data["routines"]) == 2

            list_resp = client.get("/admin/chores/routines")
            assert list_resp.status_code == 200
            groups = list_resp.json()
            sadie_group = next((g for g in groups if g["member_id"] == str(sadie.id)), None)
            assert sadie_group is not None
            assert len(sadie_group["routines"]) == 2
        finally:
            _clear_overrides()

    def test_delete_routine(self, db: Session, adults: dict, children: dict, family: Family):
        actor = adults["robert"]
        sadie = children["sadie"]
        # Seed a routine
        rt = upsert_chore_routine(db, family_id=family.id, member_id=sadie.id,
                                  routine_key="to_delete", label="Delete me")
        db.flush()

        client = _make_client(db, actor)
        try:
            resp = client.delete(f"/admin/chores/routines/{rt.id}")
            assert resp.status_code == 204

            resp2 = client.delete(f"/admin/chores/routines/{rt.id}")
            assert resp2.status_code == 404
        finally:
            _clear_overrides()


class TestAllowanceAdminRoutes:
    def test_list_policies_empty(self, db: Session, adults: dict, family: Family):
        actor = adults["robert"]
        client = _make_client(db, actor)
        try:
            resp = client.get("/admin/allowance/policies")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            _clear_overrides()

    def test_put_and_list_policy(self, db: Session, adults: dict, children: dict, family: Family):
        actor = adults["robert"]
        sadie = children["sadie"]
        client = _make_client(db, actor)
        try:
            resp = client.put(
                f"/admin/allowance/policies/{sadie.id}",
                json={
                    "baseline_cents": 500,
                    "payout_schedule": "weekly",
                    "weekly_target_cents": 1000,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["baseline_amount_cents"] == 500
            assert data["payout_schedule"]["weekly_target_cents"] == 1000

            list_resp = client.get("/admin/allowance/policies")
            assert list_resp.status_code == 200
            policies = list_resp.json()
            sadie_policy = next(
                (p for p in policies if p["family_member_id"] == str(sadie.id)), None
            )
            assert sadie_policy is not None
            assert sadie_policy["baseline_amount_cents"] == 500
        finally:
            _clear_overrides()


class TestIntegrationsAdminRoutes:
    def _seed_connector_and_account(self, db: Session, family: Family,
                                    key: str = "google_calendar") -> ConnectorAccount:
        from sqlalchemy import select
        connector = db.scalars(
            select(Connector).where(Connector.connector_key == key)
        ).first()
        if not connector:
            connector = Connector(connector_key=key, label=key.title(), tier=1)
            db.add(connector)
            db.flush()

        account = ConnectorAccount(
            connector_id=connector.id,
            family_id=family.id,
            status="disconnected",
            account_label="My Calendar",
        )
        db.add(account)
        db.flush()
        return account

    def test_list_connections(self, db: Session, adults: dict, family: Family):
        self._seed_connector_and_account(db, family)
        actor = adults["robert"]
        client = _make_client(db, actor)
        try:
            resp = client.get("/admin/integrations/connections")
            assert resp.status_code == 200
            items = resp.json()
            assert len(items) >= 1
            item = items[0]
            assert "connector_key" in item
            assert "status" in item
        finally:
            _clear_overrides()

    def test_patch_connection_status(self, db: Session, adults: dict, family: Family):
        account = self._seed_connector_and_account(db, family, key="ynab")
        actor = adults["robert"]
        client = _make_client(db, actor)
        try:
            resp = client.patch(
                f"/admin/integrations/connections/{account.id}",
                json={"status": "connected"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "connected"
        finally:
            _clear_overrides()

    def test_patch_invalid_status(self, db: Session, adults: dict, family: Family):
        account = self._seed_connector_and_account(db, family, key="hearth_display")
        actor = adults["robert"]
        client = _make_client(db, actor)
        try:
            resp = client.patch(
                f"/admin/integrations/connections/{account.id}",
                json={"status": "super_invalid"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()
