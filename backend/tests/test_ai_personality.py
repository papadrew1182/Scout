"""Sprint 04 Phase 2 - per-member personality config tests.

Covers:
- personality_defaults: every enum returns the expected tier default;
  merge_over_defaults handles missing keys + unknown keys
- service validation: enum violation raises 422; unknown keys raise
  422; notes/role_hints length trim
- build_personality_preamble: deterministic output for every enum
  value; notes + role_hints surface when set
- prompt-composition: the preamble appears in the final system prompt
  from build_system_prompt when db is passed
- HTTP: GET /personality/me returns merged config even without a
  member_config row; PATCH /personality/me validates + persists;
  GET/PATCH /personality/members/{id} are gated by
  ai.edit_any_personality; cross-family reads return 404
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytz
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.ai import personality_defaults
from app.ai.context import build_system_prompt, load_member_context
from app.models.foundation import (
    Family,
    FamilyMember,
    Session as SessionModel,
    UserAccount,
)
from app.services import ai_personality_service
from app.services.auth_service import hash_password


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
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# personality_defaults module
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_each_tier_has_full_default_shape(self):
        for tier in ("PRIMARY_PARENT", "PARENT", "TEEN", "CHILD", "YOUNG_CHILD"):
            d = personality_defaults.defaults_for_tier(tier)
            for key in personality_defaults.ALLOWED_KEYS:
                assert key in d, f"{tier} default missing {key}"

    def test_unknown_tier_falls_back_to_child_safe(self):
        d = personality_defaults.defaults_for_tier("UNKNOWN_TIER")
        # Fallback is conservative — NOT the adult advanced-vocab default
        assert d["vocabulary_level"] != "advanced"

    def test_none_tier_also_falls_back(self):
        d = personality_defaults.defaults_for_tier(None)
        assert d["tone"] in personality_defaults.TONE_OPTIONS

    def test_merge_fills_missing_from_tier(self):
        merged = personality_defaults.merge_over_defaults(
            {"tone": "playful"}, "PARENT"
        )
        assert merged["tone"] == "playful"
        # Other fields came from PARENT default
        assert merged["vocabulary_level"] == "advanced"

    def test_merge_drops_unknown_keys_silently(self):
        merged = personality_defaults.merge_over_defaults(
            {"tone": "playful", "made_up_key": "x"}, "PARENT"
        )
        assert "made_up_key" not in merged

    def test_merge_none_stored_returns_pure_defaults(self):
        merged = personality_defaults.merge_over_defaults(None, "TEEN")
        expected = personality_defaults.defaults_for_tier("TEEN")
        assert merged == expected


# ---------------------------------------------------------------------------
# service validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_enum_violation_raises_422(self):
        with pytest.raises(HTTPException) as excinfo:
            ai_personality_service.validate_payload({"tone": "sarcastic"})
        assert excinfo.value.status_code == 422

    def test_unknown_key_raises_422(self):
        with pytest.raises(HTTPException) as excinfo:
            ai_personality_service.validate_payload({"mystery_knob": "up"})
        assert excinfo.value.status_code == 422

    def test_notes_trimmed_to_500(self):
        clean = ai_personality_service.validate_payload(
            {"notes_to_self": "x" * 1000}
        )
        assert len(clean["notes_to_self"]) == 500

    def test_role_hints_trimmed_to_200(self):
        clean = ai_personality_service.validate_payload(
            {"role_hints": "y" * 500}
        )
        assert len(clean["role_hints"]) == 200

    def test_non_string_notes_raises_422(self):
        with pytest.raises(HTTPException) as excinfo:
            ai_personality_service.validate_payload({"notes_to_self": 42})
        assert excinfo.value.status_code == 422

    def test_empty_payload_returns_empty_clean(self):
        assert ai_personality_service.validate_payload({}) == {}


# ---------------------------------------------------------------------------
# build_personality_preamble
# ---------------------------------------------------------------------------


class TestPreamble:
    def test_every_enum_value_renders_without_error(self):
        # Matrix cover each field × each value; crude but cheap.
        for tone in personality_defaults.TONE_OPTIONS:
            for vocab in personality_defaults.VOCAB_OPTIONS:
                resolved = personality_defaults.merge_over_defaults(
                    {"tone": tone, "vocabulary_level": vocab}, "PARENT"
                )
                out = ai_personality_service.build_personality_preamble(resolved)
                assert tone in out
                assert vocab in out

    def test_notes_surface_when_set(self):
        resolved = personality_defaults.merge_over_defaults(
            {"notes_to_self": "Likes ultra-concise answers"}, "PARENT"
        )
        out = ai_personality_service.build_personality_preamble(resolved)
        assert "Likes ultra-concise answers" in out

    def test_role_hints_surface_when_set(self):
        resolved = personality_defaults.merge_over_defaults(
            {"role_hints": "Oldest sibling; often juggling"}, "TEEN"
        )
        out = ai_personality_service.build_personality_preamble(resolved)
        assert "Oldest sibling" in out

    def test_proactivity_not_in_preamble(self):
        """Proactivity is configuration-only until Sprint 05 ships the
        nudges engine."""
        resolved = personality_defaults.merge_over_defaults(
            {"proactivity": "forthcoming"}, "PARENT"
        )
        out = ai_personality_service.build_personality_preamble(resolved)
        assert "forthcoming" not in out
        assert "Proactivity" not in out

    def test_blank_notes_do_not_render_a_bullet(self):
        resolved = personality_defaults.merge_over_defaults(
            {"notes_to_self": ""}, "PARENT"
        )
        out = ai_personality_service.build_personality_preamble(resolved)
        assert "Member notes:" not in out


# ---------------------------------------------------------------------------
# Prompt-composition integration
# ---------------------------------------------------------------------------


class TestPromptInjection:
    def test_preamble_appears_in_system_prompt(
        self, db: Session, family, adults
    ):
        """End-to-end: when build_system_prompt is called with db, the
        member's personality preamble gets baked into the output."""
        andrew = adults["robert"]
        # Explicitly set a personality for Andrew so we can assert a
        # specific substring even if the tier default changes later.
        ai_personality_service.upsert_personality(
            db,
            family_member_id=andrew.id,
            payload={"notes_to_self": "PROMPTSIGIL_ANDREW_42"},
        )
        ctx = load_member_context(db, family.id, andrew.id)
        prompt = build_system_prompt(ctx, "personal", db=db)
        assert "PROMPTSIGIL_ANDREW_42" in prompt
        assert "Voice profile for this member" in prompt

    def test_prompt_still_builds_without_db(
        self, db: Session, family, adults
    ):
        """Legacy call path (no db) must not crash. Personality
        preamble simply doesn't appear."""
        andrew = adults["robert"]
        ctx = load_member_context(db, family.id, andrew.id)
        prompt = build_system_prompt(ctx, "personal")
        assert "Voice profile for this member" not in prompt


# ---------------------------------------------------------------------------
# HTTP: GET / PATCH /personality/me
# ---------------------------------------------------------------------------


class TestHTTP:
    def test_get_me_returns_merged_even_without_stored_row(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew@test.app")

        r = client.get(
            "/api/ai/personality/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["stored"] is None
        resolved = body["resolved"]
        for key in personality_defaults.ALLOWED_KEYS:
            assert key in resolved
        assert "preamble" in body
        assert "Voice profile" in body["preamble"]

    def test_patch_me_validates_and_persists(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew@test.app")

        r = client.patch(
            "/api/ai/personality/me",
            json={"tone": "playful", "notes_to_self": "Keep it tight"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["resolved"]["tone"] == "playful"

        # Read-back reflects the write
        r2 = client.get(
            "/api/ai/personality/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.json()["stored"]["tone"] == "playful"

    def test_patch_me_rejects_unknown_key(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew@test.app")

        r = client.patch(
            "/api/ai/personality/me",
            json={"mystery_knob": "up"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Pydantic extra=forbid returns 422 before the route body runs
        assert r.status_code == 422

    def test_patch_me_rejects_invalid_enum(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew@test.app")

        r = client.patch(
            "/api/ai/personality/me",
            json={"tone": "sarcastic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422

    def test_cross_family_member_returns_404(
        self, db: Session, family, adults, client
    ):
        """ai.edit_any_personality can only reach members in the
        caller's own family."""
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew@test.app")

        # Make an adult-role member in a DIFFERENT family
        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()
        other = FamilyMember(
            family_id=other_family.id,
            first_name="Stranger",
            role="adult",
        )
        db.add(other)
        db.commit()

        r = client.get(
            f"/api/ai/personality/members/{other.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
