"""Tests for auth service and session management.

Covers:
- login success/failure
- session persistence and expiry
- logout invalidation
- current user endpoint
- unauthorized request rejection
- child cannot escalate via session
- family isolation through auth
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.foundation import Family, FamilyMember, Session as SessionModel, UserAccount
from app.services import auth_service


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def robert_account(db: Session, adults) -> UserAccount:
    return auth_service.create_account(db, adults["robert"].id, "robert@whitfield.com", "password123")


@pytest.fixture()
def sadie_account(db: Session, children) -> UserAccount:
    return auth_service.create_account(db, children["sadie"].id, "sadie@whitfield.com", "kidpass123")


# ---------------------------------------------------------------------------
# Account creation
# ---------------------------------------------------------------------------


class TestAccountCreation:
    def test_create_account(self, db, adults):
        account = auth_service.create_account(db, adults["robert"].id, "test@test.com", "pass123")
        assert account.email == "test@test.com"
        assert account.auth_provider == "email"
        assert account.password_hash is not None
        assert account.password_hash != "pass123"  # hashed

    def test_duplicate_email_rejected(self, db, adults):
        auth_service.create_account(db, adults["robert"].id, "dup@test.com", "pass123")
        with pytest.raises(HTTPException) as exc:
            auth_service.create_account(db, adults["megan"].id, "dup@test.com", "pass456")
        assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self, db, adults, robert_account):
        result = auth_service.login(db, "robert@whitfield.com", "password123")
        assert "token" in result
        assert result["member"]["role"] == "adult"
        assert result["member"]["first_name"] == "Robert"

    def test_login_wrong_password(self, db, adults, robert_account):
        with pytest.raises(HTTPException) as exc:
            auth_service.login(db, "robert@whitfield.com", "wrong")
        assert exc.value.status_code == 401

    def test_login_nonexistent_email(self, db):
        with pytest.raises(HTTPException) as exc:
            auth_service.login(db, "nobody@test.com", "pass")
        assert exc.value.status_code == 401

    def test_login_via_route(self, client, db, adults, robert_account):
        r = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com",
            "password": "password123",
        })
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["member"]["role"] == "adult"

    def test_login_bad_password_via_route(self, client, db, adults, robert_account):
        r = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com",
            "password": "wrong",
        })
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Session resolution
# ---------------------------------------------------------------------------


class TestSession:
    def test_session_resolves(self, db, adults, robert_account):
        result = auth_service.login(db, "robert@whitfield.com", "password123")
        account, member, family = auth_service.resolve_session(db, result["token"])
        assert member.id == adults["robert"].id
        assert member.role == "adult"

    def test_invalid_token_rejected(self, db):
        with pytest.raises(HTTPException) as exc:
            auth_service.resolve_session(db, "garbage-token")
        assert exc.value.status_code == 401

    def test_expired_session_rejected(self, db, adults, robert_account):
        result = auth_service.login(db, "robert@whitfield.com", "password123")
        # Manually expire the session
        session = db.scalars(
            __import__("sqlalchemy", fromlist=["select"]).select(SessionModel)
            .where(SessionModel.token == result["token"])
        ).first()
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.flush()
        with pytest.raises(HTTPException) as exc:
            auth_service.resolve_session(db, result["token"])
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_invalidates_session(self, db, adults, robert_account):
        result = auth_service.login(db, "robert@whitfield.com", "password123")
        token = result["token"]
        auth_service.logout(db, token)
        with pytest.raises(HTTPException) as exc:
            auth_service.resolve_session(db, token)
        assert exc.value.status_code == 401

    def test_logout_via_route(self, client, db, adults, robert_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.post("/api/auth/logout", headers=_auth(token))
        assert r.status_code == 200

        # Token no longer valid
        r = client.get("/api/auth/me", headers=_auth(token))
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# /api/auth/me
# ---------------------------------------------------------------------------


class TestMe:
    def test_me_returns_actor(self, client, db, adults, robert_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.get("/api/auth/me", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert data["first_name"] == "Robert"
        assert data["role"] == "adult"
        assert data["family_name"] == "Whitfield"

    def test_me_no_token_401(self, client, db, family):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_child_me(self, client, db, children, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        token = login.json()["token"]
        r = client.get("/api/auth/me", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["role"] == "child"


# ---------------------------------------------------------------------------
# Server-derived actor enforcement
# ---------------------------------------------------------------------------


class TestActorEnforcement:
    def test_child_cannot_approve_meal_plan(self, client, db, family, adults, children, sadie_account):
        from app.services import weekly_meal_plan_service as wmp
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=date(2026, 4, 13),
            week_plan={"dinners": {"monday": {"title": "X"}}, "breakfast": {}, "lunch": {}},
            prep_plan={"tasks": [{"title": "Y"}]},
            grocery_plan={"stores": [{"name": "Z", "items": [{"title": "A"}]}]},
        )
        login = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        token = login.json()["token"]
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            headers=_auth(token),
        )
        assert r.status_code == 403

    def test_child_session_cannot_access_parent_inbox(self, client, db, family, children, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        token = login.json()["token"]
        r = client.get(
            f"/families/{family.id}/action-items/current",
            headers=_auth(token),
        )
        assert r.status_code == 403

    def test_family_isolation_via_auth(self, client, db, family, adults, robert_account):
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.get(
            f"/families/{other.id}/dashboard/personal",
            headers=_auth(token),
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


class TestPasswordChange:
    def test_change_own_password(self, client, db, adults, robert_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.post("/api/auth/password/change", json={
            "current_password": "password123",
            "new_password": "newpass456",
        }, headers=_auth(token))
        assert r.status_code == 200

        # Old password no longer works
        r2 = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        assert r2.status_code == 401

        # New password works
        r3 = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "newpass456",
        })
        assert r3.status_code == 200

    def test_wrong_current_password_rejected(self, client, db, adults, robert_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.post("/api/auth/password/change", json={
            "current_password": "wrong",
            "new_password": "newpass456",
        }, headers=_auth(token))
        assert r.status_code == 401

    def test_short_password_rejected(self, client, db, adults, robert_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.post("/api/auth/password/change", json={
            "current_password": "password123",
            "new_password": "short",
        }, headers=_auth(token))
        assert r.status_code == 422  # pydantic validation


# ---------------------------------------------------------------------------
# Admin password reset
# ---------------------------------------------------------------------------


class TestAdminPasswordReset:
    def test_admin_can_reset_child_password(self, client, db, adults, children, robert_account, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.post(f"/api/auth/accounts/{sadie_account.id}/reset-password", json={
            "account_id": str(sadie_account.id),
            "new_password": "newkidpass",
        }, headers=_auth(token))
        assert r.status_code == 200

        # Child can log in with new password
        r2 = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "newkidpass",
        })
        assert r2.status_code == 200

    def test_child_cannot_reset_password(self, client, db, adults, children, robert_account, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        token = login.json()["token"]
        r = client.post(f"/api/auth/accounts/{robert_account.id}/reset-password", json={
            "account_id": str(robert_account.id),
            "new_password": "hacked",
        }, headers=_auth(token))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


class TestSessionManagement:
    def test_list_sessions(self, client, db, adults, robert_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.get("/api/auth/sessions", headers=_auth(token))
        assert r.status_code == 200
        sessions = r.json()
        assert len(sessions) >= 1

    def test_revoke_other_sessions(self, client, db, adults, robert_account):
        # Create two sessions
        login1 = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token1 = login1.json()["token"]
        login2 = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token2 = login2.json()["token"]

        # Revoke other sessions from session 1
        r = client.post("/api/auth/sessions/revoke-others", headers=_auth(token1))
        assert r.status_code == 200
        assert r.json()["revoked"] >= 1

        # Token 2 should be invalidated
        r2 = client.get("/api/auth/me", headers=_auth(token2))
        assert r2.status_code == 401

        # Token 1 still works
        r3 = client.get("/api/auth/me", headers=_auth(token1))
        assert r3.status_code == 200


# ---------------------------------------------------------------------------
# Account management (admin)
# ---------------------------------------------------------------------------


class TestAccountManagement:
    def test_list_accounts_adult_only(self, client, db, family, adults, children, robert_account, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]
        r = client.get("/api/auth/accounts", headers=_auth(token))
        assert r.status_code == 200
        accounts = r.json()
        names = [a["first_name"] for a in accounts]
        assert "Robert" in names
        assert "Sadie" in names

    def test_child_cannot_list_accounts(self, client, db, family, adults, children, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        token = login.json()["token"]
        r = client.get("/api/auth/accounts", headers=_auth(token))
        assert r.status_code == 403

    def test_deactivate_and_activate(self, client, db, adults, children, robert_account, sadie_account):
        login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        token = login.json()["token"]

        # Deactivate
        r = client.post(f"/api/auth/accounts/{sadie_account.id}/deactivate", headers=_auth(token))
        assert r.status_code == 200

        # Child can't log in
        r2 = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        assert r2.status_code == 401

        # Reactivate
        r3 = client.post(f"/api/auth/accounts/{sadie_account.id}/activate", headers=_auth(token))
        assert r3.status_code == 200

        # Child can log in again
        r4 = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        assert r4.status_code == 200

    def test_admin_revoke_sessions(self, client, db, adults, children, robert_account, sadie_account):
        # Child logs in
        login = client.post("/api/auth/login", json={
            "email": "sadie@whitfield.com", "password": "kidpass123",
        })
        child_token = login.json()["token"]

        # Admin revokes child's sessions
        admin_login = client.post("/api/auth/login", json={
            "email": "robert@whitfield.com", "password": "password123",
        })
        admin_token = admin_login.json()["token"]
        r = client.post(f"/api/auth/accounts/{sadie_account.id}/revoke-sessions", headers=_auth(admin_token))
        assert r.status_code == 200

        # Child's token is now invalid
        r2 = client.get("/api/auth/me", headers=_auth(child_token))
        assert r2.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_rate_limit_after_many_failures(self, client, db, family):
        # Clear rate limit state
        auth_service._login_attempts.clear()
        for i in range(10):
            client.post("/api/auth/login", json={
                "email": "nobody@test.com", "password": "wrong",
            })
        r = client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "wrong",
        })
        assert r.status_code == 429
        # Cleanup
        auth_service._login_attempts.clear()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_bootstrap_creates_first_account(self, client, db, family, adults):
        r = client.post("/api/auth/bootstrap", json={
            "email": "first@family.com", "password": "firstpass",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "first@family.com"
        assert "member_id" in data

    def test_bootstrap_blocked_when_accounts_exist(self, client, db, family, adults, robert_account):
        r = client.post("/api/auth/bootstrap", json={
            "email": "second@family.com", "password": "pass123",
        })
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# Route lockdown verification
# ---------------------------------------------------------------------------


class TestRouteLockdown:
    def test_family_routes_require_auth(self, client, db, family):
        r = client.get(f"/families/{family.id}/members")
        assert r.status_code == 401

    def test_calendar_routes_require_auth(self, client, db, family):
        r = client.get(f"/families/{family.id}/events")
        assert r.status_code == 401

    def test_notes_routes_require_auth(self, client, db, family):
        r = client.get(f"/families/{family.id}/notes")
        assert r.status_code == 401

    def test_personal_tasks_require_auth(self, client, db, family):
        r = client.get(f"/families/{family.id}/personal-tasks")
        assert r.status_code == 401

    def test_finance_routes_require_auth(self, client, db, family):
        r = client.get(f"/families/{family.id}/bills")
        assert r.status_code == 401

    def test_grocery_list_requires_auth(self, client, db, family):
        r = client.get(f"/families/{family.id}/groceries/current")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# /ready endpoint
# ---------------------------------------------------------------------------


class TestReady:
    def test_ready_returns_status_fields(self, client, db, family):
        r = client.get("/ready")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ready"
        assert "environment" in data
        assert "auth_required" in data
        assert "bootstrap_enabled" in data
        assert "accounts_exist" in data
        assert "ai_available" in data
        assert "meal_generation" in data


# ---------------------------------------------------------------------------
# Bootstrap idempotency
# ---------------------------------------------------------------------------


class TestBootstrapIdempotency:
    def test_bootstrap_ignores_enable_flag_when_accounts_exist(self, client, db, family, adults, robert_account):
        """Even with enable_bootstrap=true, bootstrap returns 409 if accounts exist."""
        r = client.post("/api/auth/bootstrap", json={
            "email": "new@test.com", "password": "pass123456",
        })
        assert r.status_code == 409
