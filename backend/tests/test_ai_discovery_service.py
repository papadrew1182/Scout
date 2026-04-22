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
from app.models.nudges import NudgeDispatch, NudgeDispatchItem
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


def test_convert_proposal_stamps_occurrence_at_utc():
    """_convert_proposal must stamp occurrence_at_utc so proposals
    returned by propose_nudges are directly usable by
    resolve_occurrence_fields. Regression test for a Task 4 layering
    smell where the stamp originally lived in the tick.
    """
    from app.services.nudge_ai_discovery import _convert_proposal
    from app.schemas.nudge_discovery import DiscoveryProposal
    import uuid
    from datetime import datetime

    dp = DiscoveryProposal(
        member_id=uuid.uuid4(),
        trigger_entity_kind="personal_task",
        trigger_entity_id=uuid.uuid4(),
        scheduled_for=datetime(2026, 4, 22, 14, 30),
        severity="normal",
        body="Remember to water the plants.",
    )
    np = _convert_proposal(dp)
    assert np.context["occurrence_at_utc"] == dp.scheduled_for
    assert np.context["body"] == dp.body
    assert np.context["ai_generated"] is True
    assert np.trigger_kind == "ai_suggested"


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


# ---------------------------------------------------------------------------
# Task 4 - nudge_ai_discovery_tick (scheduler entry point)
# ---------------------------------------------------------------------------


def _silence_compose_body_ai(monkeypatch):
    """Force compose_body's orchestrator call to raise so the dispatch
    pipeline deterministically hits the fixed-template fallback. Keeps
    tick tests independent of any real AI key configuration.
    """
    from app.ai import orchestrator as orch

    def _raising(**_kwargs):
        raise RuntimeError("test: force compose_body fallback")

    monkeypatch.setattr(orch, "generate_nudge_body", _raising)


def _silence_soft_cap(monkeypatch):
    """Short-circuit the weekly soft-cap usage report used by both
    propose_nudges and compose_body. Returns a never-capped report so
    the AI path is exercised end-to-end in the tick tests."""
    monkeypatch.setattr(
        "app.ai.pricing.build_usage_report",
        lambda **_kw: {"cap_warning": False},
    )


class TestNudgeAiDiscoveryTick:
    def test_tick_iterates_all_families_and_dispatches(
        self, monkeypatch, db: Session, family: Family, adults: dict
    ):
        """Seed two families with actionable overdue tasks and assert
        the tick produces nudge_dispatches rows for both."""
        robert = adults["robert"]

        # Seed family A's overdue task (family + adults fixtures).
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=robert.id,
                title="Pay electric bill",
                status="pending",
                due_at=NOW - timedelta(hours=3),
            )
        )

        # Seed family B from scratch (conftest gives one family).
        fam_b = Family(name="Second Family", timezone="America/Chicago")
        db.add(fam_b)
        db.flush()
        parent_b = FamilyMember(
            family_id=fam_b.id,
            first_name="Jamie",
            last_name="Smith",
            role="adult",
        )
        db.add(parent_b)
        db.flush()
        db.add(
            PersonalTask(
                family_id=fam_b.id,
                assigned_to=parent_b.id,
                title="Call the plumber",
                status="pending",
                due_at=NOW - timedelta(hours=2),
            )
        )
        db.flush()

        # Map each family's overdue member into a DiscoveryProposal.
        member_by_family = {family.id: robert.id, fam_b.id: parent_b.id}

        def _fake_propose(*, family_id, digest, now_utc, **_kw):
            return [
                DiscoveryProposal(
                    member_id=member_by_family[family_id],
                    trigger_entity_kind="general",
                    scheduled_for=now_utc + timedelta(minutes=5),
                    body=f"Family {family_id} has something to do today.",
                )
            ]

        monkeypatch.setattr(
            nad.orchestrator, "propose_nudges_from_digest", _fake_propose
        )
        _silence_soft_cap(monkeypatch)
        _silence_compose_body_ai(monkeypatch)

        written = nad.nudge_ai_discovery_tick(db, NOW)

        assert written >= 2, (
            f"expected at least one dispatch per family, got {written}"
        )

        # Children from both families landed.
        items = (
            db.query(NudgeDispatchItem)
            .filter(NudgeDispatchItem.trigger_kind == "ai_suggested")
            .all()
        )
        member_ids_touched = {item.family_member_id for item in items}
        assert robert.id in member_ids_touched
        assert parent_b.id in member_ids_touched

        # Parent rows exist for both families (via the member join).
        parent_member_ids = {
            d.family_member_id
            for d in db.query(NudgeDispatch).all()
        }
        assert robert.id in parent_member_ids
        assert parent_b.id in parent_member_ids

    def test_tick_logs_and_continues_when_one_family_raises(
        self, monkeypatch, db: Session, family: Family, adults: dict
    ):
        """Family A's propose_nudges raises; family B still dispatches.
        The tick must swallow the failure and continue."""
        robert = adults["robert"]

        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=robert.id,
                title="Broken task",
                status="pending",
                due_at=NOW - timedelta(hours=1),
            )
        )

        fam_b = Family(name="Healthy Family", timezone="America/Chicago")
        db.add(fam_b)
        db.flush()
        parent_b = FamilyMember(
            family_id=fam_b.id,
            first_name="Sam",
            role="adult",
        )
        db.add(parent_b)
        db.flush()
        db.add(
            PersonalTask(
                family_id=fam_b.id,
                assigned_to=parent_b.id,
                title="Healthy-family task",
                status="pending",
                due_at=NOW - timedelta(hours=1),
            )
        )
        db.flush()

        fam_a_id = family.id

        real_propose = nad.propose_nudges

        def _guarded_propose(db_arg, family_id, now_utc):
            if family_id == fam_a_id:
                raise RuntimeError("boom")
            return real_propose(db_arg, family_id, now_utc)

        monkeypatch.setattr(nad, "propose_nudges", _guarded_propose)

        def _fake_orch(*, family_id, digest, now_utc, **_kw):
            return [
                DiscoveryProposal(
                    member_id=parent_b.id,
                    trigger_entity_kind="general",
                    scheduled_for=now_utc + timedelta(minutes=7),
                    body="Healthy-family ai suggestion.",
                )
            ]

        monkeypatch.setattr(
            nad.orchestrator, "propose_nudges_from_digest", _fake_orch
        )
        _silence_soft_cap(monkeypatch)
        _silence_compose_body_ai(monkeypatch)

        # Must not raise despite family A blowing up.
        written = nad.nudge_ai_discovery_tick(db, NOW)

        assert written >= 1

        touched = {
            d.family_member_id
            for d in db.query(NudgeDispatch).all()
        }
        assert parent_b.id in touched
        assert robert.id not in touched

    def test_tick_returns_zero_when_no_families(
        self, monkeypatch, db: Session
    ):
        """Empty families table: tick must complete cleanly and return 0."""
        calls: list = []

        def _fake_orch(**_kw):
            calls.append(1)
            return []

        monkeypatch.setattr(
            nad.orchestrator, "propose_nudges_from_digest", _fake_orch
        )
        _silence_soft_cap(monkeypatch)
        _silence_compose_body_ai(monkeypatch)

        written = nad.nudge_ai_discovery_tick(db, NOW)

        assert written == 0
        assert calls == []

    def test_tick_returns_zero_when_all_throttled(
        self, monkeypatch, db: Session, family: Family, adults: dict
    ):
        """Pre-mark the family as having just run AI discovery. Orchestrator
        must not be called and the tick returns 0."""
        robert = adults["robert"]
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=robert.id,
                title="Would-be trigger",
                status="pending",
                due_at=NOW - timedelta(hours=2),
            )
        )
        db.flush()

        # Pre-load the in-memory throttle state so propose_nudges
        # short-circuits on _is_throttled and never reaches the
        # orchestrator.
        nad._last_ai_discovery_run_utc[family.id] = NOW

        calls: list = []

        def _fake_orch(**_kw):
            calls.append(1)
            return []

        monkeypatch.setattr(
            nad.orchestrator, "propose_nudges_from_digest", _fake_orch
        )
        _silence_soft_cap(monkeypatch)
        _silence_compose_body_ai(monkeypatch)

        written = nad.nudge_ai_discovery_tick(db, NOW)

        assert written == 0
        assert calls == []
