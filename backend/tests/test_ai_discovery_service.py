"""Sprint 05 Phase 5 Task 2 - nudge_ai_discovery service tests.

Covers:
  - build_family_state_digest: scope, caps, exclusion of ai_messages /
    connector_configs / health_summaries.
  - _is_throttled: per-family, 1h window, side-effect-free.
  - propose_nudges: throttle gate, cap gate, empty-digest short-circuit,
    DiscoveryProposal -> NudgeProposal conversion (specific-entity and
    'general' -> 'ai_discovery' remap).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.calendar import Event, EventAttendee
from app.models.connectors import ConnectorConfig
from app.models.foundation import Family, FamilyMember
from app.models.health_fitness import HealthSummary
from app.models.life_management import Routine, TaskInstance
from app.models.personal_tasks import PersonalTask
from app.schemas.nudge_discovery import DiscoveryProposal
from app.services import nudge_ai_discovery as nad


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_discovery_state():
    """Module-level dict leaks across tests; clear both before and after."""
    nad._last_ai_discovery_run_utc.clear()
    yield
    nad._last_ai_discovery_run_utc.clear()


def _naive_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


NOW = datetime(2026, 4, 21, 14, 30, 0)  # naive UTC, matches production shape


# ---------------------------------------------------------------------------
# build_family_state_digest
# ---------------------------------------------------------------------------


def test_digest_excludes_ai_messages_and_connectors_and_health(
    db: Session, family: Family, adults: dict
):
    """Seed rows in every source the plan forbids; none may leak into digest."""
    robert = adults["robert"]

    # ai_messages (requires a parent ai_conversations row)
    conv = AIConversation(
        family_id=family.id,
        family_member_id=robert.id,
        surface="personal",
    )
    db.add(conv)
    db.flush()
    db.add(
        AIMessage(
            conversation_id=conv.id,
            role="user",
            content="please remind me about trash day",
        )
    )

    # connector_configs (family-scoped)
    db.add(
        ConnectorConfig(
            family_id=family.id,
            connector_name="ynab",
            scope="family",
            sync_direction="read",
            authority_level="secondary",
        )
    )

    # health_summaries
    db.add(
        HealthSummary(
            family_id=family.id,
            family_member_id=robert.id,
            summary_date=date(2026, 4, 20),
            steps=8000,
        )
    )
    db.flush()

    digest = nad.build_family_state_digest(db, family.id, NOW)

    # The digest schema itself only has these keys; assert the exact shape
    # so any future accidental field addition (e.g., "ai_messages") shows up.
    assert set(digest.keys()) == {
        "family_id",
        "now_utc",
        "members",
        "overdue_tasks",
        "upcoming_tasks_24h",
        "upcoming_events_24h",
        "recent_missed_routines_3d",
        "active_routines",
    }
    # Stringify once and scan for forbidden table/column fingerprints.
    serialized = str(digest)
    assert "please remind me about trash day" not in serialized
    assert "ynab" not in serialized
    assert "8000" not in serialized


def test_digest_includes_overdue_and_upcoming_tasks(
    db: Session, family: Family, adults: dict
):
    robert = adults["robert"]

    overdue = PersonalTask(
        family_id=family.id,
        assigned_to=robert.id,
        title="Pay electric bill",
        status="pending",
        due_at=NOW - timedelta(hours=5),
    )
    upcoming = PersonalTask(
        family_id=family.id,
        assigned_to=robert.id,
        title="Pick up dry cleaning",
        status="pending",
        due_at=NOW + timedelta(hours=6),
    )
    # A completed task that would otherwise match the window must be filtered.
    done = PersonalTask(
        family_id=family.id,
        assigned_to=robert.id,
        title="Already done",
        status="done",
        due_at=NOW - timedelta(hours=2),
        completed_at=NOW - timedelta(hours=1),
    )
    db.add_all([overdue, upcoming, done])
    db.flush()

    digest = nad.build_family_state_digest(db, family.id, NOW)

    overdue_titles = [t["title"] for t in digest["overdue_tasks"]]
    upcoming_titles = [t["title"] for t in digest["upcoming_tasks_24h"]]

    assert "Pay electric bill" in overdue_titles
    assert "Already done" not in overdue_titles
    assert "Pick up dry cleaning" in upcoming_titles
    assert digest["overdue_tasks"][0]["overdue_hours"] == 5.0


def test_digest_caps_each_section_at_25(
    db: Session, family: Family, adults: dict
):
    robert = adults["robert"]
    for i in range(30):
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=robert.id,
                title=f"Overdue task {i}",
                status="pending",
                due_at=NOW - timedelta(hours=1 + i),
            )
        )
    db.flush()

    digest = nad.build_family_state_digest(db, family.id, NOW)
    assert len(digest["overdue_tasks"]) == 25


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------


def test_is_throttled_blocks_second_call_within_hour():
    fam_id = uuid.uuid4()
    t0 = datetime(2026, 4, 21, 10, 0, 0)

    assert nad._is_throttled(fam_id, t0) is False
    nad._mark_discovery_ran(fam_id, t0)

    assert nad._is_throttled(fam_id, t0 + timedelta(minutes=30)) is True
    assert nad._is_throttled(fam_id, t0 + timedelta(minutes=59, seconds=59)) is True
    assert nad._is_throttled(fam_id, t0 + timedelta(minutes=61)) is False


def test_is_throttled_is_per_family():
    fam_a = uuid.uuid4()
    fam_b = uuid.uuid4()
    t0 = datetime(2026, 4, 21, 10, 0, 0)

    nad._mark_discovery_ran(fam_a, t0)

    assert nad._is_throttled(fam_a, t0 + timedelta(minutes=10)) is True
    assert nad._is_throttled(fam_b, t0 + timedelta(minutes=10)) is False


# ---------------------------------------------------------------------------
# propose_nudges
# ---------------------------------------------------------------------------


def _seed_one_overdue(db: Session, family: Family, member: FamilyMember) -> None:
    """Minimum viable actionable digest so propose_nudges does not
    short-circuit on empty state."""
    db.add(
        PersonalTask(
            family_id=family.id,
            assigned_to=member.id,
            title="Mow the lawn",
            status="pending",
            due_at=NOW - timedelta(hours=3),
        )
    )
    db.flush()


def test_propose_nudges_respects_throttle(
    monkeypatch, db: Session, family: Family, adults: dict
):
    robert = adults["robert"]
    _seed_one_overdue(db, family, robert)

    calls = []

    def _fake_propose(*, family_id, digest, now_utc, **_kw):
        calls.append(family_id)
        return [
            DiscoveryProposal(
                member_id=robert.id,
                trigger_entity_kind="general",
                scheduled_for=NOW + timedelta(minutes=5),
                body="Don't forget to mow the lawn today.",
            )
        ]

    # Monkeypatch the attribute on the service module (not the orchestrator
    # module) because the service imported ``orchestrator`` as a name.
    monkeypatch.setattr(
        nad.orchestrator, "propose_nudges_from_digest", _fake_propose
    )
    # Silence the usage-report gate - not relevant to this test.
    monkeypatch.setattr(
        "app.ai.pricing.build_usage_report",
        lambda **_kw: {"cap_warning": False},
    )

    first = nad.propose_nudges(db, family.id, NOW)
    second = nad.propose_nudges(db, family.id, NOW + timedelta(minutes=30))

    assert len(first) == 1
    assert second == []
    assert len(calls) == 1


def test_propose_nudges_respects_cap(
    monkeypatch, db: Session, family: Family, adults: dict
):
    robert = adults["robert"]
    _seed_one_overdue(db, family, robert)

    calls = []

    def _fake_propose(**_kw):
        calls.append(1)
        return []

    monkeypatch.setattr(
        nad.orchestrator, "propose_nudges_from_digest", _fake_propose
    )
    monkeypatch.setattr(
        "app.ai.pricing.build_usage_report",
        lambda **_kw: {"cap_warning": True},
    )

    out = nad.propose_nudges(db, family.id, NOW)

    assert out == []
    assert calls == []


def test_propose_nudges_skips_when_digest_is_empty(
    monkeypatch, db: Session, family: Family, adults: dict
):
    """Members alone are not actionable; zero items across all time-bound
    sections must bypass the orchestrator."""
    # adults fixture seeds members but NO tasks/events/instances/routines.
    calls = []

    def _fake_propose(**_kw):
        calls.append(1)
        return []

    monkeypatch.setattr(
        nad.orchestrator, "propose_nudges_from_digest", _fake_propose
    )
    monkeypatch.setattr(
        "app.ai.pricing.build_usage_report",
        lambda **_kw: {"cap_warning": False},
    )

    out = nad.propose_nudges(db, family.id, NOW)

    assert out == []
    assert calls == []
    # Throttle must NOT be consumed on empty-digest skip, so a later
    # non-empty digest in the same hour still gets a chance.
    assert nad._is_throttled(family.id, NOW + timedelta(minutes=5)) is False


def test_propose_nudges_converts_discovery_to_nudge_proposal(
    monkeypatch, db: Session, family: Family, adults: dict
):
    robert = adults["robert"]
    _seed_one_overdue(db, family, robert)

    entity_id = uuid.uuid4()

    def _fake_propose(**_kw):
        return [
            DiscoveryProposal(
                member_id=robert.id,
                trigger_entity_kind="personal_task",
                trigger_entity_id=entity_id,
                scheduled_for=NOW + timedelta(minutes=10),
                severity="high",
                body="Electric bill payment is overdue.",
            )
        ]

    monkeypatch.setattr(
        nad.orchestrator, "propose_nudges_from_digest", _fake_propose
    )
    monkeypatch.setattr(
        "app.ai.pricing.build_usage_report",
        lambda **_kw: {"cap_warning": False},
    )

    out = nad.propose_nudges(db, family.id, NOW)

    assert len(out) == 1
    np = out[0]
    assert np.family_member_id == robert.id
    assert np.trigger_kind == "ai_suggested"
    assert np.trigger_entity_kind == "personal_task"
    assert np.trigger_entity_id == entity_id
    assert np.severity == "high"
    assert np.context["body"] == "Electric bill payment is overdue."
    assert np.context["ai_generated"] is True


def test_propose_nudges_maps_general_kind_to_ai_discovery(
    monkeypatch, db: Session, family: Family, adults: dict
):
    robert = adults["robert"]
    _seed_one_overdue(db, family, robert)

    def _fake_propose(**_kw):
        return [
            DiscoveryProposal(
                member_id=robert.id,
                trigger_entity_kind="general",
                trigger_entity_id=None,
                scheduled_for=NOW + timedelta(minutes=15),
                body="Consider reviewing this week's meal plan.",
            )
        ]

    monkeypatch.setattr(
        nad.orchestrator, "propose_nudges_from_digest", _fake_propose
    )
    monkeypatch.setattr(
        "app.ai.pricing.build_usage_report",
        lambda **_kw: {"cap_warning": False},
    )

    out = nad.propose_nudges(db, family.id, NOW)

    assert len(out) == 1
    assert out[0].trigger_entity_kind == "ai_discovery"
    assert out[0].trigger_entity_id is None


# ---------------------------------------------------------------------------
# Additional digest coverage (events + missed routines) - ensures query
# shape matches production schema before wiring into scheduler in Task 3.
# ---------------------------------------------------------------------------


def test_digest_includes_events_with_attendees(
    db: Session, family: Family, adults: dict
):
    robert = adults["robert"]
    megan = adults["megan"]

    event = Event(
        family_id=family.id,
        title="Vet appointment",
        starts_at=NOW + timedelta(hours=3),
        ends_at=NOW + timedelta(hours=4),
    )
    db.add(event)
    db.flush()
    db.add_all(
        [
            EventAttendee(event_id=event.id, family_member_id=robert.id),
            EventAttendee(event_id=event.id, family_member_id=megan.id),
        ]
    )
    db.flush()

    digest = nad.build_family_state_digest(db, family.id, NOW)

    assert len(digest["upcoming_events_24h"]) == 1
    entry = digest["upcoming_events_24h"][0]
    assert entry["title"] == "Vet appointment"
    assert set(entry["attendees"]) == {str(robert.id), str(megan.id)}


def test_digest_recent_missed_routines_respects_3d_window(
    db: Session, family: Family, children: dict, sadie_routines: list
):
    sadie = children["sadie"]
    morning = sadie_routines[0]

    # Within window: missed 1 day ago
    db.add(
        TaskInstance(
            family_id=family.id,
            family_member_id=sadie.id,
            routine_id=morning.id,
            instance_date=(NOW - timedelta(days=1)).date(),
            due_at=NOW - timedelta(days=1),
            is_completed=False,
        )
    )
    # Outside window: missed 5 days ago
    db.add(
        TaskInstance(
            family_id=family.id,
            family_member_id=sadie.id,
            routine_id=morning.id,
            instance_date=(NOW - timedelta(days=5)).date(),
            due_at=NOW - timedelta(days=5),
            is_completed=False,
        )
    )
    db.flush()

    digest = nad.build_family_state_digest(db, family.id, NOW)

    assert len(digest["recent_missed_routines_3d"]) == 1
    assert digest["recent_missed_routines_3d"][0]["routine_name"] == "Sadie Morning"
