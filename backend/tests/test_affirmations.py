"""Tests for the affirmation selection engine and feedback logic."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.affirmations import Affirmation, AffirmationDeliveryLog, AffirmationFeedback
from app.models.access import HouseholdRule
from app.models.foundation import Family, FamilyMember


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_affirmation_tables(db):
    """Remove seed affirmations from migration 039 so tests start clean."""
    db.execute(text("DELETE FROM scout.affirmation_delivery_log"))
    db.execute(text("DELETE FROM scout.affirmation_feedback"))
    db.execute(text("DELETE FROM scout.affirmations"))
    db.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_affirmations(db: Session, count: int = 5, **overrides) -> list[Affirmation]:
    affs = []
    for i in range(count):
        a = Affirmation(
            text=f"Affirmation {i}",
            category="growth",
            tone="encouraging",
            philosophy="discipline",
            audience_type=overrides.get("audience_type", "general"),
            active=overrides.get("active", True),
        )
        db.add(a)
        affs.append(a)
    db.flush()
    return affs


def _seed_config(db: Session, family_id: uuid.UUID, **config_overrides) -> HouseholdRule:
    default_config = {
        "enabled": True,
        "cooldown_days": 3,
        "max_repeat_window_days": 30,
        "dynamic_generation_enabled": False,
        "moderation_required": False,
        "default_audience": "general",
        "weight_heart_boost": 1.5,
        "weight_preference_match": 1.3,
    }
    default_config.update(config_overrides)
    rule = HouseholdRule(
        family_id=family_id,
        rule_key="affirmations.config",
        rule_value=default_config,
    )
    db.add(rule)
    db.flush()
    return rule


# ---------------------------------------------------------------------------
# Selection engine tests
# ---------------------------------------------------------------------------

class TestSelectAffirmation:

    def test_returns_affirmation_when_pool_available(self, db, family, adults):
        _seed_affirmations(db, 5)
        _seed_config(db, family.id)
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is not None
        assert result["affirmation"]["text"].startswith("Affirmation")
        assert result["delivery_id"] is not None

    def test_returns_none_when_disabled_family(self, db, family, adults):
        _seed_affirmations(db, 5)
        _seed_config(db, family.id, enabled=False)
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is None

    def test_returns_none_when_disabled_member(self, db, family, adults):
        from app.models.access import MemberConfig
        _seed_affirmations(db, 5)
        _seed_config(db, family.id)
        mc = MemberConfig(
            family_member_id=adults["robert"].id,
            key="affirmations.preferences",
            value={"enabled": False},
        )
        db.add(mc)
        db.flush()
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is None

    def test_excludes_thumbs_downed(self, db, family, adults):
        affs = _seed_affirmations(db, 1)
        _seed_config(db, family.id)
        fb = AffirmationFeedback(
            family_member_id=adults["robert"].id,
            affirmation_id=affs[0].id,
            reaction_type="thumbs_down",
        )
        db.add(fb)
        db.flush()
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is None

    def test_thumbs_down_then_reshow_restores(self, db, family, adults):
        affs = _seed_affirmations(db, 1)
        _seed_config(db, family.id)
        now = datetime.now(timezone.utc)
        db.add(AffirmationFeedback(
            family_member_id=adults["robert"].id,
            affirmation_id=affs[0].id,
            reaction_type="thumbs_down",
            created_at=now - timedelta(hours=1),
        ))
        db.add(AffirmationFeedback(
            family_member_id=adults["robert"].id,
            affirmation_id=affs[0].id,
            reaction_type="reshow",
            created_at=now,
        ))
        db.flush()
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is not None

    def test_respects_cooldown(self, db, family, adults):
        affs = _seed_affirmations(db, 1)
        _seed_config(db, family.id, cooldown_days=7)
        now = datetime.now(timezone.utc)
        db.add(AffirmationDeliveryLog(
            family_member_id=adults["robert"].id,
            affirmation_id=affs[0].id,
            surfaced_at=now - timedelta(days=2),
            surfaced_in="today",
        ))
        db.flush()
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is None

    def test_audience_filtering_child_sees_child_and_general(self, db, family, children):
        _seed_affirmations(db, 2, audience_type="parent")
        child_affs = _seed_affirmations(db, 1, audience_type="child")
        _seed_config(db, family.id)
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, children["sadie"].id, family.id)
        assert result is not None
        assert result["affirmation"]["id"] == str(child_affs[0].id)

    def test_returns_none_when_no_active_affirmations(self, db, family, adults):
        _seed_affirmations(db, 3, active=False)
        _seed_config(db, family.id)
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is None

    def test_logs_delivery(self, db, family, adults):
        _seed_affirmations(db, 3)
        _seed_config(db, family.id)
        from app.services.affirmation_engine import select_affirmation
        result = select_affirmation(db, adults["robert"].id, family.id)
        assert result is not None
        logs = db.query(AffirmationDeliveryLog).filter_by(
            family_member_id=adults["robert"].id
        ).all()
        assert len(logs) == 1
        assert logs[0].affirmation_id == uuid.UUID(result["affirmation"]["id"])


class TestAffirmationAnalytics:

    def test_analytics_returns_counts(self, db, family, adults):
        affs = _seed_affirmations(db, 3)
        for a in affs:
            db.add(AffirmationDeliveryLog(
                family_member_id=adults["robert"].id,
                affirmation_id=a.id,
                surfaced_at=datetime.now(timezone.utc),
                surfaced_in="today",
            ))
        db.add(AffirmationFeedback(
            family_member_id=adults["robert"].id,
            affirmation_id=affs[0].id,
            reaction_type="heart",
        ))
        db.add(AffirmationFeedback(
            family_member_id=adults["robert"].id,
            affirmation_id=affs[1].id,
            reaction_type="thumbs_down",
        ))
        db.flush()
        from app.services.affirmation_engine import get_affirmation_analytics
        stats = get_affirmation_analytics(db, family.id)
        assert stats["total_deliveries"] == 3
        assert stats["reactions"]["heart"] == 1
        assert stats["reactions"]["thumbs_down"] == 1
        assert len(stats["most_liked"]) >= 1
