"""Regression coverage for the parent-only family-member + user-account
maintenance endpoints added by the standalone fix PR:

    PATCH /families/{fid}/members/{mid}                (core fields)
    GET   /families/{fid}/members/{mid}/accounts       (list logins)
    POST  /families/{fid}/members/{mid}/accounts       (add a login)
    PATCH /families/{fid}/members/{mid}/accounts/{aid} (rotate email / etc.)

Invariant under test: every mutation must leave at least one active
adult with at least one active user_account. A change that would
drop the family below that threshold returns 409.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import (
    FamilyMember,
    Session as SessionModel,
    UserAccount,
)
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(db: Session, member_id, email: str, is_primary: bool = True) -> UserAccount:
    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=email,
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=is_primary,
        is_active=True,
    )
    db.add(account)
    db.flush()
    return account


def _bearer_for(db: Session, member_id, email: str | None = None) -> str:
    email = email or f"mm-{uuid.uuid4().hex[:8]}@scout.local"
    _make_account(db, member_id, email)
    token = f"tok-{uuid.uuid4().hex}"
    db.add(
        SessionModel(
            user_account_id=db.scalars(
                select(UserAccount).where(UserAccount.email == email)
            ).first().id,
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
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# PATCH core fields
# ---------------------------------------------------------------------------


class TestMemberCoreUpdate:
    def test_adult_can_edit_child_core_fields(
        self, client, db: Session, family, adults, children
    ):
        tok = _bearer_for(db, adults["robert"].id)
        sadie = children["sadie"]
        r = client.patch(
            f"/families/{family.id}/members/{sadie.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "first_name": "Sadie",
                "last_name": "RenamedRoberts",
                "birthdate": "2012-09-10",
                "role": "child",
                "is_active": True,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["last_name"] == "RenamedRoberts"
        assert body["birthdate"] == "2012-09-10"

    def test_child_cannot_edit_members(
        self, client, db: Session, family, adults, children
    ):
        # Make sure an adult has a login so the invariant is satisfied
        _make_account(db, adults["robert"].id, "robert-inv@scout.local")
        tok = _bearer_for(db, children["sadie"].id)
        townes = children["townes"]
        r = client.patch(
            f"/families/{family.id}/members/{townes.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"first_name": "Townie"},
        )
        assert r.status_code == 403

    def test_empty_first_name_rejected(
        self, client, db: Session, family, adults, children
    ):
        tok = _bearer_for(db, adults["robert"].id)
        sadie = children["sadie"]
        r = client.patch(
            f"/families/{family.id}/members/{sadie.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"first_name": "   "},
        )
        assert r.status_code == 400

    def test_cannot_demote_last_adult_member(
        self, client, db: Session, family, adults
    ):
        # Only Robert has a login. Demoting him to child leaves zero
        # active adults with accounts → 409.
        robert = adults["robert"]
        tok = _bearer_for(db, robert.id)
        r = client.patch(
            f"/families/{family.id}/members/{robert.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"role": "child"},
        )
        assert r.status_code == 409
        db.refresh(robert)
        assert robert.role == "adult"  # rolled back

    def test_cannot_deactivate_last_adult_member(
        self, client, db: Session, family, adults
    ):
        robert = adults["robert"]
        tok = _bearer_for(db, robert.id)
        r = client.patch(
            f"/families/{family.id}/members/{robert.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"is_active": False},
        )
        assert r.status_code == 409
        db.refresh(robert)
        assert robert.is_active is True

    def test_can_demote_when_another_adult_still_has_login(
        self, client, db: Session, family, adults
    ):
        robert = adults["robert"]
        megan = adults["megan"]
        # Give Megan a login too so Robert can safely become a child.
        _make_account(db, megan.id, "megan-signin@scout.local")
        tok = _bearer_for(db, robert.id)
        r = client.patch(
            f"/families/{family.id}/members/{robert.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"role": "child"},
        )
        assert r.status_code == 200
        db.refresh(robert)
        assert robert.role == "child"


# ---------------------------------------------------------------------------
# POST create member
# ---------------------------------------------------------------------------


class TestCreateMember:
    def test_adult_can_create_new_member(
        self, client, db: Session, family, adults
    ):
        tok = _bearer_for(db, adults["robert"].id)
        r = client.post(
            f"/families/{family.id}/members",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "first_name": "Willie",
                "last_name": "Roberts",
                "role": "child",
                "birthdate": "2020-05-10",
            },
        )
        assert r.status_code == 201
        body = r.json()
        assert body["first_name"] == "Willie"
        assert body["role"] == "child"

    def test_child_cannot_create_member(
        self, client, db: Session, family, adults, children
    ):
        _make_account(db, adults["robert"].id, "robert-inv2@scout.local")
        tok = _bearer_for(db, children["sadie"].id)
        r = client.post(
            f"/families/{family.id}/members",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "first_name": "Ghost",
                "role": "child",
            },
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Accounts CRUD
# ---------------------------------------------------------------------------


class TestMemberAccounts:
    def test_adult_can_list_and_create_account_on_child(
        self, client, db: Session, family, adults, children
    ):
        tok = _bearer_for(db, adults["robert"].id)
        sadie = children["sadie"]

        # Initially empty.
        r = client.get(
            f"/families/{family.id}/members/{sadie.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        assert r.json() == []

        # Create one.
        create = client.post(
            f"/families/{family.id}/members/{sadie.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": "sadie-new@scout.local", "password": "longenough12"},
        )
        assert create.status_code == 201
        body = create.json()
        assert body["email"] == "sadie-new@scout.local"
        assert body["is_active"] is True

        # And the list now has it.
        r2 = client.get(
            f"/families/{family.id}/members/{sadie.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert len(r2.json()) == 1

    def test_child_cannot_view_or_create_accounts(
        self, client, db: Session, family, adults, children
    ):
        _make_account(db, adults["robert"].id, "robert-inv3@scout.local")
        tok = _bearer_for(db, children["sadie"].id)
        townes = children["townes"]
        r_list = client.get(
            f"/families/{family.id}/members/{townes.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r_list.status_code == 403
        r_post = client.post(
            f"/families/{family.id}/members/{townes.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": "t@scout.local", "password": "abc12345"},
        )
        assert r_post.status_code == 403

    def test_duplicate_email_returns_409(
        self, client, db: Session, family, adults, children
    ):
        tok = _bearer_for(db, adults["robert"].id)
        sadie = children["sadie"]
        client.post(
            f"/families/{family.id}/members/{sadie.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": "dup@scout.local", "password": "longenough12"},
        )
        r2 = client.post(
            f"/families/{family.id}/members/{sadie.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": "dup@scout.local", "password": "longenough12"},
        )
        assert r2.status_code == 409

    def test_short_password_rejected(
        self, client, db: Session, family, adults, children
    ):
        tok = _bearer_for(db, adults["robert"].id)
        sadie = children["sadie"]
        r = client.post(
            f"/families/{family.id}/members/{sadie.id}/accounts",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": "short@scout.local", "password": "short"},
        )
        assert r.status_code == 422  # pydantic min_length

    def test_email_rotation_and_password_reset(
        self, client, db: Session, family, adults
    ):
        robert = adults["robert"]
        tok = _bearer_for(db, robert.id, email="robert-rotate@scout.local")
        # Find the account we just created.
        acct = db.scalars(
            select(UserAccount).where(UserAccount.family_member_id == robert.id)
        ).first()

        r = client.patch(
            f"/families/{family.id}/members/{robert.id}/accounts/{acct.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "email": "robert-rotated@scout.local",
                "new_password": "freshpass789",
            },
        )
        assert r.status_code == 200
        assert r.json()["email"] == "robert-rotated@scout.local"

    def test_cannot_deactivate_last_active_adult_account(
        self, client, db: Session, family, adults
    ):
        robert = adults["robert"]
        tok = _bearer_for(db, robert.id, email="robert-last@scout.local")
        acct = db.scalars(
            select(UserAccount).where(UserAccount.family_member_id == robert.id)
        ).first()
        r = client.patch(
            f"/families/{family.id}/members/{robert.id}/accounts/{acct.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"is_active": False},
        )
        assert r.status_code == 409
        db.refresh(acct)
        assert acct.is_active is True  # rolled back

    def test_can_deactivate_stale_account_when_another_active(
        self, client, db: Session, family, adults
    ):
        robert = adults["robert"]
        tok = _bearer_for(db, robert.id, email="robert-primary@scout.local")
        # Add a second account for the same member.
        stale = _make_account(
            db, robert.id, "robert-stale@scout.local", is_primary=False
        )
        db.commit()
        r = client.patch(
            f"/families/{family.id}/members/{robert.id}/accounts/{stale.id}",
            headers={"Authorization": f"Bearer {tok}"},
            json={"is_active": False},
        )
        assert r.status_code == 200
        db.refresh(stale)
        assert stale.is_active is False
