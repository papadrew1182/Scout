# Sprint 05 Phase 1 — Core Nudge Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the core proactive-nudges engine: three built-in triggers (overdue_task, upcoming_event, missed_routine), an Action Inbox + push delivery path, a per-member proactivity gate, and dedupe via a unique key.

**Architecture:** One new service module `backend/app/services/nudges_service.py` with pure-function scanners (return `NudgeProposal` dataclasses from read-only SQL), a proactivity gate, and a `dispatch()` sink that writes `nudge_dispatches` rows and fans out to `parent_action_items` + `push_service.send_push`. Wired into the existing APScheduler tick in `backend/app/scheduler.py` as `_run_nudge_scan`. Idempotent via a UNIQUE `dedupe_key` on `nudge_dispatches`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, PostgreSQL 16, APScheduler (already present), pytest, existing `push_service.send_push`.

**Precondition:** Sprint 04 Phase 2 merged (`member_config['ai.personality']` holds `proactivity`). Live as of commit `16325d3f`.

**Reference spec:** `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md` §Phase 1. Amendments in §7 of that doc apply here.

---

## File structure

**New files:**
- `backend/migrations/049_nudge_engine.sql` — create `scout.nudge_dispatches`, register `nudges.view_own` perm.
- `database/migrations/049_nudge_engine.sql` — byte-identical mirror of the above.
- `backend/app/models/nudges.py` — SQLAlchemy model `NudgeDispatch`.
- `backend/app/services/nudges_service.py` — `NudgeProposal` dataclass, `scan_*` functions, `apply_proactivity`, `dispatch`, `run_nudge_scan`.
- `backend/tests/test_nudges.py` — all phase-1 tests.

**Modified files:**
- `backend/app/scheduler.py` — add `_run_nudge_scan` callable and wire it inside the existing tick.

**No frontend changes in Phase 1.** The `/settings/ai` Recent nudges card and the `/admin/scout-ai` quiet-hours control ship in Phase 2. Smoke spec also lands in Phase 2 alongside the `/api/nudges/me` route.

---

## Task 1 — Migration 049 (schema + permission)

**Files:**
- Create: `backend/migrations/049_nudge_engine.sql`
- Create: `database/migrations/049_nudge_engine.sql`

- [ ] **Step 1: Write `backend/migrations/049_nudge_engine.sql`**

```sql
-- Migration 049: Sprint 05 Phase 1 - proactive nudges core engine
--
-- Creates scout.nudge_dispatches and registers nudges.view_own for
-- all user tiers (YOUNG_CHILD through PRIMARY_PARENT; DISPLAY_ONLY
-- excluded by the existing convention).
--
-- Dedupe: one row per (member, trigger_kind, entity, day). The
-- UNIQUE (dedupe_key) constraint is the source of idempotency; a
-- second tick that would produce the same key no-ops on INSERT.

BEGIN;

CREATE TABLE IF NOT EXISTS scout.nudge_dispatches (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id        uuid        NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    trigger_kind            text        NOT NULL,
    trigger_entity_kind     text        NOT NULL,
    trigger_entity_id       uuid,
    proactivity_at_dispatch text        NOT NULL,
    lead_time_minutes       integer     NOT NULL DEFAULT 0,
    scheduled_for           timestamptz NOT NULL,
    dispatched_at           timestamptz,
    parent_action_item_id   uuid        REFERENCES public.parent_action_items(id) ON DELETE SET NULL,
    push_delivery_id        uuid,
    delivered_channels      jsonb       NOT NULL DEFAULT '[]'::jsonb,
    dedupe_key              text        NOT NULL,
    severity                text        NOT NULL DEFAULT 'normal',
    suppressed_reason       text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_nudge_dispatches_trigger_kind
        CHECK (trigger_kind IN ('overdue_task','upcoming_event','missed_routine','custom_rule','ai_suggested')),
    CONSTRAINT chk_nudge_dispatches_severity
        CHECK (severity IN ('low','normal','high')),
    CONSTRAINT uq_nudge_dispatches_dedupe
        UNIQUE (dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_nudge_dispatches_member_scheduled
    ON scout.nudge_dispatches (family_member_id, scheduled_for DESC);

CREATE INDEX IF NOT EXISTS idx_nudge_dispatches_pending
    ON scout.nudge_dispatches (scheduled_for)
    WHERE dispatched_at IS NULL;

CREATE TRIGGER trg_nudge_dispatches_updated_at
    BEFORE UPDATE ON scout.nudge_dispatches
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Permission: nudges.view_own for all user tiers.
INSERT INTO scout.permissions (permission_key, description) VALUES
    ('nudges.view_own', 'View own recent proactive nudge dispatches')
ON CONFLICT (permission_key) DO NOTHING;

INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD','CHILD','TEEN','PARENT','PRIMARY_PARENT')
  AND p.permission_key = 'nudges.view_own'
ON CONFLICT DO NOTHING;

COMMIT;
```

- [ ] **Step 2: Mirror to `database/migrations/`**

Run:
```bash
cp backend/migrations/049_nudge_engine.sql database/migrations/049_nudge_engine.sql
diff backend/migrations/049_nudge_engine.sql database/migrations/049_nudge_engine.sql
```
Expected: no diff output (identical).

- [ ] **Step 3: Apply locally against the test DB to catch SQL errors**

Run (from repo root, with a local postgres running):
```bash
SCOUT_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/scout_test" py backend/migrate.py
```
Expected: `Applied 049_nudge_engine.sql` followed by `All migrations complete.` No SQL errors.

- [ ] **Step 4: Verify the table and index exist**

Run:
```bash
SCOUT_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/scout_test" py -c "import psycopg2, os; c=psycopg2.connect(os.environ['SCOUT_DATABASE_URL']); cur=c.cursor(); cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_schema='scout' AND table_name='nudge_dispatches' ORDER BY column_name\"); print([r[0] for r in cur.fetchall()])"
```
Expected list includes: `created_at`, `dedupe_key`, `delivered_channels`, `dispatched_at`, `family_member_id`, `id`, `lead_time_minutes`, `parent_action_item_id`, `proactivity_at_dispatch`, `push_delivery_id`, `scheduled_for`, `severity`, `suppressed_reason`, `trigger_entity_id`, `trigger_entity_kind`, `trigger_kind`, `updated_at`.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/049_nudge_engine.sql database/migrations/049_nudge_engine.sql
git commit -m "migration: Sprint 05 Phase 1 nudge engine schema (049)

Creates scout.nudge_dispatches with a UNIQUE (dedupe_key) constraint
for idempotency and registers nudges.view_own for all user tiers.
No data seeded; the table is populated by the scheduler tick.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — NudgeDispatch SQLAlchemy model

**Files:**
- Create: `backend/app/models/nudges.py`

- [ ] **Step 1: Write `backend/app/models/nudges.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NudgeDispatch(Base):
    __tablename__ = "nudge_dispatches"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False
    )
    trigger_kind: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_entity_kind: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    proactivity_at_dispatch: Mapped[str] = mapped_column(Text, nullable=False)
    lead_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scheduled_for: Mapped[datetime] = mapped_column(nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column()
    parent_action_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_action_items.id", ondelete="SET NULL")
    )
    push_delivery_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    delivered_channels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    suppressed_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
```

- [ ] **Step 2: Verify model imports cleanly**

Run:
```bash
cd backend && py -c "from app.models.nudges import NudgeDispatch; print(NudgeDispatch.__tablename__, NudgeDispatch.__table_args__)"
```
Expected: `nudge_dispatches {'schema': 'scout'}`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/nudges.py
git commit -m "backend: NudgeDispatch SQLAlchemy model for Sprint 05 Phase 1

Matches migration 049 schema exactly. Uses schema='scout' since the
table lives in the scout schema, unlike ai_conversations which sits
in public. The push_delivery_id is plain uuid (no FK) because
push_deliveries is in public and Sprint 03 didn't add a schema=scout
version.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — NudgeProposal dataclass + skeleton service

**Files:**
- Create: `backend/app/services/nudges_service.py`

- [ ] **Step 1: Write the service skeleton**

```python
"""Sprint 05 Phase 1 - proactive nudges core engine.

Scanners return NudgeProposal dataclasses (pure-function read-only SQL).
apply_proactivity gates them per the caller's member_config setting.
dispatch() is the sink that writes nudge_dispatches rows and fans out
to the Action Inbox + push_service. run_nudge_scan() chains them for
the scheduler tick.

Idempotency is guaranteed by the UNIQUE (dedupe_key) constraint on
nudge_dispatches — a repeat tick that would produce the same key
no-ops on INSERT (we use ON CONFLICT DO NOTHING equivalents or catch
IntegrityError and continue).

Fixed copy templates ship here in Phase 1. Phase 3 replaces them with
AI-composed per-member copy.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.nudges import NudgeDispatch

logger = logging.getLogger("scout.nudges")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class NudgeProposal:
    """A scanner's output before proactivity gate and dispatch.
    Serializable and easy to inspect in tests."""

    family_member_id: uuid.UUID
    trigger_kind: str          # overdue_task | upcoming_event | missed_routine
    trigger_entity_kind: str   # personal_task | event | task_instance
    trigger_entity_id: uuid.UUID | None
    scheduled_for: datetime
    severity: str = "normal"
    # Copy context (title, time string, etc.) used by the template renderer
    context: dict[str, Any] = field(default_factory=dict)


# Placeholder functions. Each later task fills them in.
def scan_overdue_tasks(db: Session, now_utc: datetime) -> list[NudgeProposal]:
    return []


def scan_upcoming_events(db: Session, now_utc: datetime, lead_minutes: int = 30) -> list[NudgeProposal]:
    return []


def scan_missed_routines(db: Session, now_utc: datetime) -> list[NudgeProposal]:
    return []


def apply_proactivity(
    db: Session, proposals: list[NudgeProposal], now_utc: datetime
) -> list[NudgeProposal]:
    return proposals


def dispatch(db: Session, proposals: list[NudgeProposal], now_utc: datetime) -> int:
    return 0


def run_nudge_scan(db: Session, now_utc: datetime | None = None) -> int:
    """Entry point for the scheduler. Returns the number of new
    dispatches written this tick."""
    ts = now_utc or _utcnow()
    proposals: list[NudgeProposal] = []
    proposals.extend(scan_overdue_tasks(db, ts))
    proposals.extend(scan_upcoming_events(db, ts))
    proposals.extend(scan_missed_routines(db, ts))
    gated = apply_proactivity(db, proposals, ts)
    return dispatch(db, gated, ts)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/nudges_service.py
git commit -m "backend: nudges_service skeleton (dataclass + entry points)

Stub functions wired into a single run_nudge_scan entry point. Each
scanner and the dispatcher land in their own subsequent commits so
per-task TDD stays clean and a failure is easy to bisect.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — scan_overdue_tasks (TDD)

**Files:**
- Create: `backend/tests/test_nudges.py`
- Modify: `backend/app/services/nudges_service.py:55-57`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_nudges.py
"""Sprint 05 Phase 1 - nudges engine tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.personal_tasks import PersonalTask
from app.services import nudges_service


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestScanOverdueTasks:
    def test_overdue_task_produces_one_proposal_for_the_assignee(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
        task = PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="Take out the trash",
            status="pending",
            due_at=now - timedelta(hours=1),
        )
        db.add(task)
        db.commit()

        proposals = nudges_service.scan_overdue_tasks(db, now)

        assert len(proposals) == 1
        p = proposals[0]
        assert p.family_member_id == andrew.id
        assert p.trigger_kind == "overdue_task"
        assert p.trigger_entity_kind == "personal_task"
        assert p.trigger_entity_id == task.id
        assert p.context["title"] == "Take out the trash"

    def test_completed_task_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Already done",
                status="done",
                due_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=1),
            )
        )
        db.commit()

        assert nudges_service.scan_overdue_tasks(db, now) == []

    def test_future_task_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Later",
                status="pending",
                due_at=now + timedelta(hours=3),
            )
        )
        db.commit()

        assert nudges_service.scan_overdue_tasks(db, now) == []
```

- [ ] **Step 2: Run and verify it fails**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestScanOverdueTasks -v
```
Expected: all three tests FAIL — the first with `AssertionError: 0 == 1` because the stub returns `[]`; the other two coincidentally PASS but do not exercise real logic. (The first test must fail; this is the test that drives the implementation.)

- [ ] **Step 3: Implement `scan_overdue_tasks` in `nudges_service.py`**

Replace the stub:

```python
def scan_overdue_tasks(db: Session, now_utc: datetime) -> list[NudgeProposal]:
    """Emit one proposal per active personal_tasks row whose due_at
    has passed. The proposal's scheduled_for is the due_at itself —
    the nudge is already "due" when the scanner sees it; lead time
    doesn't apply to overdue (you can't nudge before something was
    overdue)."""
    rows = db.execute(
        text(
            """
            SELECT id, assigned_to, title, due_at
            FROM personal_tasks
            WHERE status != 'done'
              AND due_at IS NOT NULL
              AND due_at < :now
            """
        ),
        {"now": now_utc},
    ).all()
    proposals: list[NudgeProposal] = []
    for row in rows:
        proposals.append(
            NudgeProposal(
                family_member_id=row.assigned_to,
                trigger_kind="overdue_task",
                trigger_entity_kind="personal_task",
                trigger_entity_id=row.id,
                scheduled_for=row.due_at,
                context={
                    "title": row.title,
                    "due_time": row.due_at.strftime("%I:%M %p"),
                },
            )
        )
    return proposals
```

- [ ] **Step 4: Run and verify it passes**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestScanOverdueTasks -v
```
Expected: all three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_nudges.py backend/app/services/nudges_service.py
git commit -m "backend: scan_overdue_tasks returns one proposal per overdue task

Pure SQL read; no side effects. Scheduled_for uses the original due_at
so dispatch can dedupe by (member, kind, entity, date) even across
scheduler clock drift.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — scan_upcoming_events (TDD)

**Files:**
- Modify: `backend/tests/test_nudges.py` (append class)
- Modify: `backend/app/services/nudges_service.py` (replace stub `scan_upcoming_events`)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_nudges.py`:

```python
from app.models.calendar import Event, EventAttendee


class TestScanUpcomingEvents:
    def test_event_within_lead_window_produces_proposal_for_each_attendee(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        megan = adults["megan"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Pediatrician appointment",
            starts_at=now + timedelta(minutes=20),
            ends_at=now + timedelta(minutes=50),
        )
        db.add(event)
        db.flush()
        db.add_all(
            [
                EventAttendee(event_id=event.id, family_member_id=andrew.id),
                EventAttendee(event_id=event.id, family_member_id=megan.id),
            ]
        )
        db.commit()

        proposals = nudges_service.scan_upcoming_events(db, now, lead_minutes=30)

        assert len(proposals) == 2
        member_ids = {p.family_member_id for p in proposals}
        assert member_ids == {andrew.id, megan.id}
        for p in proposals:
            assert p.trigger_kind == "upcoming_event"
            assert p.trigger_entity_kind == "event"
            assert p.trigger_entity_id == event.id
            assert p.context["title"] == "Pediatrician appointment"

    def test_event_outside_lead_window_is_ignored(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Way out",
            starts_at=now + timedelta(hours=5),
            ends_at=now + timedelta(hours=6),
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []

    def test_past_event_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Already happened",
            starts_at=now - timedelta(hours=1),
            ends_at=now - timedelta(minutes=30),
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []

    def test_cancelled_event_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Cancelled",
            starts_at=now + timedelta(minutes=15),
            ends_at=now + timedelta(minutes=45),
            is_cancelled=True,
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []
```

- [ ] **Step 2: Run and verify it fails**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestScanUpcomingEvents -v
```
Expected: `test_event_within_lead_window_produces_proposal_for_each_attendee` FAILS with `AssertionError: 0 == 2`; the three negative cases coincidentally PASS against the stub.

- [ ] **Step 3: Implement `scan_upcoming_events`**

Replace the stub:

```python
def scan_upcoming_events(
    db: Session, now_utc: datetime, lead_minutes: int = 30
) -> list[NudgeProposal]:
    """Events starting within lead_minutes of now produce one proposal
    per attendee. Past and cancelled events are excluded. All-day
    events are excluded (they have no meaningful heads-up moment)."""
    horizon = now_utc + timedelta(minutes=lead_minutes)
    rows = db.execute(
        text(
            """
            SELECT e.id, e.title, e.starts_at, ea.family_member_id
            FROM events e
            JOIN event_attendees ea ON ea.event_id = e.id
            WHERE e.is_cancelled = false
              AND e.all_day = false
              AND e.starts_at > :now
              AND e.starts_at <= :horizon
            """
        ),
        {"now": now_utc, "horizon": horizon},
    ).all()
    proposals: list[NudgeProposal] = []
    for row in rows:
        proposals.append(
            NudgeProposal(
                family_member_id=row.family_member_id,
                trigger_kind="upcoming_event",
                trigger_entity_kind="event",
                trigger_entity_id=row.id,
                scheduled_for=row.starts_at - timedelta(minutes=lead_minutes),
                context={
                    "title": row.title,
                    "start_time": row.starts_at.strftime("%I:%M %p"),
                },
            )
        )
    return proposals
```

- [ ] **Step 4: Run and verify it passes**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestScanUpcomingEvents -v
```
Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_nudges.py backend/app/services/nudges_service.py
git commit -m "backend: scan_upcoming_events emits one proposal per attendee

Joins events to event_attendees; skips past, cancelled, and all-day
rows. scheduled_for is starts_at minus lead_minutes so the proposal
carries the intended lead-time intact through apply_proactivity.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — scan_missed_routines (TDD)

**Files:**
- Modify: `backend/tests/test_nudges.py` (append class)
- Modify: `backend/app/services/nudges_service.py` (replace stub `scan_missed_routines`)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_nudges.py`:

```python
from datetime import date
from app.models.life_management import Routine, TaskInstance


class TestScanMissedRoutines:
    def _make_routine(self, db, family, member, name="Morning routine"):
        from datetime import time

        r = Routine(
            family_id=family.id,
            family_member_id=member.id,
            name=name,
            block="morning",
            recurrence="daily",
            due_time_weekday=time(7, 30),
            due_time_weekend=time(9, 0),
        )
        db.add(r)
        db.flush()
        return r

    def test_missed_routine_today_produces_proposal(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        instance = TaskInstance(
            family_id=family.id,
            family_member_id=sadie.id,
            routine_id=routine.id,
            instance_date=now.date(),
            due_at=now - timedelta(minutes=20),  # 20 min past due
            is_completed=False,
        )
        db.add(instance)
        db.commit()

        proposals = nudges_service.scan_missed_routines(db, now)

        assert len(proposals) == 1
        p = proposals[0]
        assert p.family_member_id == sadie.id
        assert p.trigger_kind == "missed_routine"
        assert p.trigger_entity_kind == "task_instance"
        assert p.trigger_entity_id == instance.id
        assert p.context["name"] == "Morning routine"

    def test_completed_routine_is_ignored(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=routine.id,
                instance_date=now.date(),
                due_at=now - timedelta(minutes=20),
                is_completed=True,
                completed_at=now - timedelta(minutes=5),
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []

    def test_override_completed_is_treated_as_completed(
        self, db: Session, family, children
    ):
        """effective_completed honors override_completed; scanner must too."""
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=routine.id,
                instance_date=now.date(),
                due_at=now - timedelta(minutes=20),
                is_completed=False,
                override_completed=True,
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []

    def test_future_due_routine_is_ignored(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=routine.id,
                instance_date=now.date(),
                due_at=now + timedelta(minutes=30),
                is_completed=False,
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []

    def test_chore_template_instance_ignored(
        self, db: Session, family, children
    ):
        """scan_missed_routines is routine-only (chore_templates produce
        their own trigger later). Ignore task_instances with routine_id
        NULL."""
        sadie = children["sadie"]
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=None,
                chore_template_id=None,
                instance_date=now.date(),
                due_at=now - timedelta(minutes=20),
                is_completed=False,
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []
```

- [ ] **Step 2: Run and verify it fails**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestScanMissedRoutines -v
```
Expected: `test_missed_routine_today_produces_proposal` FAILS. Others coincidentally PASS against the stub.

- [ ] **Step 3: Implement `scan_missed_routines`**

Replace the stub:

```python
def scan_missed_routines(
    db: Session, now_utc: datetime
) -> list[NudgeProposal]:
    """task_instances rows with a routine_id whose due_at has passed
    and are not completed (respecting override_completed). 15-minute
    lead-after-miss is baked into dispatch; here we just emit one
    proposal per missed instance."""
    rows = db.execute(
        text(
            """
            SELECT ti.id,
                   ti.family_member_id,
                   ti.due_at,
                   r.name AS routine_name
            FROM task_instances ti
            JOIN routines r ON r.id = ti.routine_id
            WHERE ti.routine_id IS NOT NULL
              AND ti.is_completed = false
              AND COALESCE(ti.override_completed, false) = false
              AND ti.due_at < :now
            """
        ),
        {"now": now_utc},
    ).all()
    proposals: list[NudgeProposal] = []
    for row in rows:
        proposals.append(
            NudgeProposal(
                family_member_id=row.family_member_id,
                trigger_kind="missed_routine",
                trigger_entity_kind="task_instance",
                trigger_entity_id=row.id,
                scheduled_for=row.due_at + timedelta(minutes=15),
                context={
                    "name": row.routine_name,
                    "due_time": row.due_at.strftime("%I:%M %p"),
                },
            )
        )
    return proposals
```

- [ ] **Step 4: Run and verify it passes**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestScanMissedRoutines -v
```
Expected: all five tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_nudges.py backend/app/services/nudges_service.py
git commit -m "backend: scan_missed_routines honors is_completed + override

Routine-only; chore_template instances get their own scanner later.
effective_completed semantics (override_completed wins) preserved
via COALESCE in the WHERE clause. Lead-after-miss of 15 min baked
into scheduled_for; apply_proactivity adjusts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — apply_proactivity (TDD)

**Files:**
- Modify: `backend/tests/test_nudges.py` (append class)
- Modify: `backend/app/services/nudges_service.py` (replace stub `apply_proactivity`)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_nudges.py`:

```python
from app.services import ai_personality_service


def _set_proactivity(db, member_id, value):
    ai_personality_service.upsert_personality(
        db, family_member_id=member_id, payload={"proactivity": value}
    )


class TestApplyProactivity:
    def test_quiet_drops_all_proposals(self, db: Session, family, adults):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "quiet")
        now = _utcnow()
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now,
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert out == []

    def test_balanced_is_passthrough(self, db: Session, family, adults):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "balanced")
        now = _utcnow()
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="upcoming_event",
            trigger_entity_kind="event",
            trigger_entity_id=None,
            scheduled_for=now + timedelta(minutes=30),
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == prop.scheduled_for

    def test_forthcoming_doubles_lead_for_upcoming_events(
        self, db: Session, family, adults
    ):
        """forthcoming moves the scheduled_for 2x earlier for
        upcoming_event (30 min lead -> 60 min lead)."""
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "forthcoming")
        now = _utcnow()
        # Original: lead 30 -> scheduled_for = starts_at - 30 = (now + 0)
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="upcoming_event",
            trigger_entity_kind="event",
            trigger_entity_id=None,
            scheduled_for=now,
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        # scheduled_for shifts earlier by 30 min (original lead)
        assert out[0].scheduled_for == now - timedelta(minutes=30)

    def test_forthcoming_halves_missed_routine_lead(
        self, db: Session, family, adults
    ):
        """forthcoming drops missed-routine lead from 15 min to ~5 min
        (implementation: subtract 10 min from scheduled_for)."""
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "forthcoming")
        now = _utcnow()
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="missed_routine",
            trigger_entity_kind="task_instance",
            trigger_entity_id=None,
            scheduled_for=now,  # already scheduled for now (due_at + 15)
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == now - timedelta(minutes=10)

    def test_forthcoming_does_not_shift_overdue_task(
        self, db: Session, family, adults
    ):
        """overdue_task scheduled_for is the original due_at — you
        cannot be earlier than already-overdue. Pass through."""
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "forthcoming")
        now = _utcnow()
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now - timedelta(hours=1),
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == prop.scheduled_for
```

- [ ] **Step 2: Run and verify it fails**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestApplyProactivity -v
```
Expected: `test_quiet_drops_all_proposals` and the two `forthcoming_*_shift` tests FAIL.

- [ ] **Step 3: Implement `apply_proactivity`**

Replace the stub:

```python
_FORTHCOMING_SHIFT_MINUTES = {
    "upcoming_event": 30,   # original lead is 30, forthcoming doubles it
    "missed_routine": 10,   # original lead-after-miss is 15, forthcoming -> 5
    # overdue_task: 0. Cannot fire earlier than "already overdue".
}


def apply_proactivity(
    db: Session, proposals: list[NudgeProposal], now_utc: datetime
) -> list[NudgeProposal]:
    """Gate + lead-time adjust per member proactivity. quiet drops all
    proposals. balanced is pass-through. forthcoming shifts
    scheduled_for earlier for triggers that support earlier firing.

    Annotates each surviving proposal with the proactivity setting
    (used by dispatch for the nudge_dispatches.proactivity_at_dispatch
    column)."""
    out: list[NudgeProposal] = []
    member_settings_cache: dict[uuid.UUID, str] = {}
    for prop in proposals:
        setting = member_settings_cache.get(prop.family_member_id)
        if setting is None:
            resolved = ai_personality_service.get_resolved_config(
                db, prop.family_member_id
            )
            setting = resolved.get("proactivity", "balanced")
            member_settings_cache[prop.family_member_id] = setting

        if setting == "quiet":
            continue

        shifted = prop
        if setting == "forthcoming":
            shift = _FORTHCOMING_SHIFT_MINUTES.get(prop.trigger_kind, 0)
            if shift > 0:
                shifted = NudgeProposal(
                    family_member_id=prop.family_member_id,
                    trigger_kind=prop.trigger_kind,
                    trigger_entity_kind=prop.trigger_entity_kind,
                    trigger_entity_id=prop.trigger_entity_id,
                    scheduled_for=prop.scheduled_for - timedelta(minutes=shift),
                    severity=prop.severity,
                    context={**prop.context, "proactivity": setting},
                )

        # Stamp the proactivity setting on the proposal's context so
        # dispatch can record it without a second DB roundtrip.
        shifted.context.setdefault("proactivity", setting)
        out.append(shifted)
    return out
```

And add the import at the top of `nudges_service.py` (below the existing imports):

```python
from app.services import ai_personality_service
```

- [ ] **Step 4: Run and verify it passes**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestApplyProactivity -v
```
Expected: all five tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_nudges.py backend/app/services/nudges_service.py
git commit -m "backend: apply_proactivity gate + forthcoming lead shifts

quiet drops proposals. balanced is pass-through. forthcoming shifts
scheduled_for earlier for upcoming_event (-30 min) and missed_routine
(-10 min). overdue_task is not shifted because 'earlier than already
overdue' is meaningless. Member setting is cached per-call so large
batches don't hammer get_resolved_config.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — dispatch: dedupe + Inbox + push (TDD)

**Files:**
- Modify: `backend/tests/test_nudges.py` (append class)
- Modify: `backend/app/services/nudges_service.py` (replace stub `dispatch`)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_nudges.py`:

```python
from app.models.action_items import ParentActionItem
from app.models.nudges import NudgeDispatch
from app.models.push import PushDevice


class TestDispatch:
    def test_writes_inbox_row_and_nudge_dispatch(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now - timedelta(minutes=5),
            context={"title": "Bins out", "due_time": "08:00 AM", "proactivity": "balanced"},
        )

        written = nudges_service.dispatch(db, [prop], now)
        db.commit()

        assert written == 1
        dispatches = list(
            db.query(NudgeDispatch)
            .filter(NudgeDispatch.family_member_id == andrew.id)
            .all()
        )
        assert len(dispatches) == 1
        d = dispatches[0]
        assert d.trigger_kind == "overdue_task"
        assert d.proactivity_at_dispatch == "balanced"
        assert "inbox" in d.delivered_channels
        assert d.parent_action_item_id is not None
        inbox = db.get(ParentActionItem, d.parent_action_item_id)
        assert inbox is not None
        assert "Bins out" in inbox.title or "Bins out" in (inbox.detail or "")

    def test_dispatch_is_idempotent_on_repeat(
        self, db: Session, family, adults
    ):
        """Second call with the same proposal is a no-op. dedupe_key
        UNIQUE constraint guarantees it."""
        andrew = adults["robert"]
        now = _utcnow()
        entity_id = uuid.uuid4()
        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=entity_id,
            scheduled_for=now,
            context={"title": "t", "due_time": "08:00 AM", "proactivity": "balanced"},
        )

        first = nudges_service.dispatch(db, [prop], now)
        db.commit()
        second = nudges_service.dispatch(db, [prop], now)
        db.commit()

        assert first == 1
        assert second == 0
        count = db.query(NudgeDispatch).filter(
            NudgeDispatch.trigger_entity_id == entity_id
        ).count()
        assert count == 1

    def test_dispatch_sends_push_when_device_exists(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PushDevice(
                family_member_id=andrew.id,
                expo_push_token="ExponentPushToken[fake]",
                device_label="iPhone",
                platform="ios",
                is_active=True,
                last_registered_at=now,
            )
        )
        db.commit()

        sent: list[dict] = []

        def fake_send_push(db, **kwargs):
            sent.append(kwargs)
            # Return a shape compatible with push_service.send_push
            # (delivery_ids + accepted_count) so dispatch can store the id.
            return type(
                "FakeResult",
                (),
                {
                    "delivery_ids": [uuid.uuid4()],
                    "accepted_count": 1,
                    "error_count": 0,
                    "notification_group_id": uuid.uuid4(),
                },
            )()

        from app.services import push_service

        monkeypatch.setattr(push_service, "send_push", fake_send_push)

        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now,
            context={"title": "t", "due_time": "08:00 AM", "proactivity": "balanced"},
        )

        nudges_service.dispatch(db, [prop], now)
        db.commit()

        assert len(sent) == 1
        d = db.query(NudgeDispatch).filter(
            NudgeDispatch.family_member_id == andrew.id
        ).first()
        assert "push" in d.delivered_channels
        assert d.push_delivery_id is not None

    def test_no_push_when_no_active_device(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        now = _utcnow()

        sent: list[dict] = []

        def fake_send_push(db, **kwargs):
            sent.append(kwargs)
            raise AssertionError("should not be called")

        from app.services import push_service

        monkeypatch.setattr(push_service, "send_push", fake_send_push)

        prop = NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now,
            context={"title": "t", "due_time": "08:00 AM", "proactivity": "balanced"},
        )

        nudges_service.dispatch(db, [prop], now)
        db.commit()

        assert sent == []
        d = db.query(NudgeDispatch).filter(
            NudgeDispatch.family_member_id == andrew.id
        ).first()
        assert "inbox" in d.delivered_channels
        assert "push" not in d.delivered_channels
        assert d.push_delivery_id is None
```

- [ ] **Step 2: Run and verify it fails**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestDispatch -v
```
Expected: all four tests FAIL — the stub returns 0 and writes nothing.

- [ ] **Step 3: Implement `dispatch`**

Replace the stub (and add imports near the top):

```python
from app.models.action_items import ParentActionItem
from app.models.push import PushDevice
from app.services import push_service
from sqlalchemy.exc import IntegrityError


_TEMPLATES = {
    "overdue_task":    "Reminder: {title} was due at {due_time}.",
    "upcoming_event":  "Heads up: {title} at {start_time}.",
    "missed_routine":  "{name} hasn't been checked off yet (was due at {due_time}).",
}


def _build_copy(proposal: NudgeProposal) -> tuple[str, str]:
    """Return (title, body) for the Inbox row + push payload. Phase 1
    uses fixed templates; Phase 3 replaces this with AI-composed copy."""
    template = _TEMPLATES.get(proposal.trigger_kind, "Scout nudge")
    body = template.format(**proposal.context)
    # Title is a short inbox-line summary; body has the details.
    title_prefix = {
        "overdue_task": "Overdue",
        "upcoming_event": "Starting soon",
        "missed_routine": "Routine check",
    }.get(proposal.trigger_kind, "Scout")
    title = f"{title_prefix}: {proposal.context.get('title') or proposal.context.get('name') or ''}".strip(": ")
    return title, body


def _dedupe_key(proposal: NudgeProposal) -> str:
    """member:kind:entity:date string. AI-suggested proposals with a
    null entity_id hash the body to get a stable key."""
    entity_part = str(proposal.trigger_entity_id) if proposal.trigger_entity_id else "null"
    date_part = proposal.scheduled_for.date().isoformat()
    return f"{proposal.family_member_id}:{proposal.trigger_kind}:{entity_part}:{date_part}"


def dispatch(
    db: Session, proposals: list[NudgeProposal], now_utc: datetime
) -> int:
    """Write nudge_dispatches + parent_action_items rows. Send push
    to active devices. Idempotent via UNIQUE (dedupe_key) — a repeat
    proposal is caught on INSERT and the savepoint rolls back.

    Uses a SAVEPOINT (db.begin_nested()) per proposal so that one
    proposal's rollback (e.g., a dedupe-key race loss) does NOT
    undo previously-successful proposals earlier in the same call.
    The outer transaction is left to the caller — the scheduler tick
    commits after run_nudge_scan returns. This keeps the test
    fixture's transaction-per-test rollback pattern intact.

    Push sends happen inside the savepoint; a push provider error is
    swallowed (logged) so Inbox remains authoritative and the
    dispatch row still commits.

    Returns the count of newly-written dispatches."""
    written = 0
    for proposal in proposals:
        key = _dedupe_key(proposal)
        # Pre-check avoids the DB exception path in the common case
        existing = db.query(NudgeDispatch).filter_by(dedupe_key=key).first()
        if existing is not None:
            continue

        title, body = _build_copy(proposal)

        try:
            with db.begin_nested():
                # 1. Inbox row first (ground truth even if push fails).
                inbox = ParentActionItem(
                    family_id=_family_id_for_member(db, proposal.family_member_id),
                    created_by_member_id=proposal.family_member_id,
                    action_type=f"nudge.{proposal.trigger_kind}",
                    title=title,
                    detail=body,
                    entity_type=proposal.trigger_entity_kind,
                    entity_id=proposal.trigger_entity_id,
                    status="pending",
                )
                db.add(inbox)
                db.flush()
                delivered: list[str] = ["inbox"]
                push_delivery_id: uuid.UUID | None = None

                # 2. Push: best-effort. Any failure logs and continues.
                active_device = (
                    db.query(PushDevice)
                    .filter(
                        PushDevice.family_member_id == proposal.family_member_id,
                        PushDevice.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if active_device is not None:
                    try:
                        result = push_service.send_push(
                            db,
                            family_member_id=proposal.family_member_id,
                            category=f"nudge.{proposal.trigger_kind}",
                            title=title,
                            body=body,
                            data={
                                "route_hint": _route_hint(proposal),
                                "trigger_kind": proposal.trigger_kind,
                            },
                            trigger_source="nudge_scan",
                        )
                        if result.delivery_ids:
                            push_delivery_id = result.delivery_ids[0]
                            delivered.append("push")
                    except Exception as e:
                        logger.exception(
                            "nudge_push_failed member=%s err=%s",
                            proposal.family_member_id, e,
                        )

                # 3. nudge_dispatches row. IntegrityError here rolls back
                #    the whole savepoint (inbox included).
                nd = NudgeDispatch(
                    family_member_id=proposal.family_member_id,
                    trigger_kind=proposal.trigger_kind,
                    trigger_entity_kind=proposal.trigger_entity_kind,
                    trigger_entity_id=proposal.trigger_entity_id,
                    proactivity_at_dispatch=proposal.context.get("proactivity", "balanced"),
                    lead_time_minutes=0,
                    scheduled_for=proposal.scheduled_for,
                    dispatched_at=now_utc,
                    parent_action_item_id=inbox.id,
                    push_delivery_id=push_delivery_id,
                    delivered_channels=delivered,
                    dedupe_key=key,
                    severity=proposal.severity,
                )
                db.add(nd)
                db.flush()  # forces INSERT and surfaces IntegrityError
            written += 1
        except IntegrityError:
            # Savepoint auto-rolled back on exception inside the with.
            continue
    return written


def _family_id_for_member(db: Session, member_id: uuid.UUID) -> uuid.UUID:
    row = db.execute(
        text("SELECT family_id FROM family_members WHERE id = :mid"),
        {"mid": member_id},
    ).first()
    if row is None:
        raise ValueError(f"family_members row missing for {member_id}")
    return row[0]


def _route_hint(proposal: NudgeProposal) -> str:
    """Deep-link the tap-to-open destination. Falls back to /today."""
    if proposal.trigger_kind == "overdue_task" and proposal.trigger_entity_id:
        return f"/today?task={proposal.trigger_entity_id}"
    if proposal.trigger_kind == "upcoming_event" and proposal.trigger_entity_id:
        return f"/calendar?event={proposal.trigger_entity_id}"
    return "/today"
```

- [ ] **Step 4: Run and verify it passes**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestDispatch -v
```
Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_nudges.py backend/app/services/nudges_service.py
git commit -m "backend: dispatch writes Inbox + push + nudge_dispatches rows

Idempotent via UNIQUE (dedupe_key) with a pre-check + IntegrityError
fallback for race conditions. Inbox is ground truth; push is
best-effort and its failure is logged, not fatal. delivered_channels
reflects what actually went through.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — Scheduler wiring + end-to-end tick test

**Files:**
- Modify: `backend/app/scheduler.py` (add `_run_nudge_scan` + wire into the tick)
- Modify: `backend/tests/test_nudges.py` (append end-to-end class)

- [ ] **Step 1: Find the existing tick function**

Run:
```bash
grep -n "_run_morning_brief\|_run_anomaly_scan\|def _tick\|run_morning_brief_tick\|run_anomaly_scan_tick" backend/app/scheduler.py
```
Note the line numbers for the next edit.

- [ ] **Step 2: Add `run_nudge_scan_tick` helper in `nudges_service.py`**

The existing scheduler pattern wraps each runner in its own try/commit/except/rollback/finally/close inside `_tick`. Each runner is a plain function that does the work and lets exceptions propagate (the tick handles rollback). So `nudges_service` should expose the same shape that `morning_brief` and `anomaly_scan` do. Rename / re-export if needed:

```python
# In backend/app/services/nudges_service.py, keep run_nudge_scan as-is
# and add a tick-named alias so the scheduler's call-site reads naturally:
def run_nudge_scan_tick(db: Session, now_utc: datetime) -> None:
    """Scheduler tick entry point. Exceptions propagate to the tick's
    outer try/except/rollback — do NOT catch here."""
    count = run_nudge_scan(db, now_utc=now_utc)
    logger.info("nudge_scan_tick count=%s", count)
```

- [ ] **Step 3: Wire the call into `_tick` using the existing per-runner pattern**

Add the import at the top of `scheduler.py` (grouped with other `app.services` imports):

```python
from app.services import nudges_service
```

Inside the existing `_tick` function, after the `anomaly_scan` block (or wherever the last runner sits), add a new block that mirrors the existing pattern exactly:

```python
            db = db_factory()
            try:
                nudges_service.run_nudge_scan_tick(db, now_utc=now_utc)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("nudge_scan_tick_failed: %s", e)
            finally:
                db.close()
```

Use the exact same `db = db_factory()` → try/commit/except/rollback/log/finally/close shape the other runners use. Each runner gets its own fresh session; a failure in one does not poison the next.

- [ ] **Step 4: Write the end-to-end test**

Append to `backend/tests/test_nudges.py`:

```python
class TestEndToEndTick:
    def test_run_nudge_scan_integrates_scanners_and_dispatch(
        self, db: Session, family, adults, children, monkeypatch
    ):
        """Single call to run_nudge_scan picks up an overdue task and
        writes a nudge_dispatches row. Smoke test of the whole
        scan -> proactivity -> dispatch chain."""
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="End-to-end",
                status="pending",
                due_at=now - timedelta(minutes=10),
            )
        )
        db.commit()

        def fake_send_push(db, **kwargs):
            return type(
                "R", (),
                {"delivery_ids": [], "accepted_count": 0, "error_count": 0,
                 "notification_group_id": uuid.uuid4()},
            )()

        from app.services import push_service
        monkeypatch.setattr(push_service, "send_push", fake_send_push)

        written = nudges_service.run_nudge_scan(db, now_utc=now)
        db.commit()

        assert written == 1
        d = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert d.trigger_kind == "overdue_task"
        assert "inbox" in d.delivered_channels

    def test_quiet_member_gets_no_dispatches(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "quiet")
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Should be silent",
                status="pending",
                due_at=now - timedelta(hours=1),
            )
        )
        db.commit()

        written = nudges_service.run_nudge_scan(db, now_utc=now)
        db.commit()

        assert written == 0
        count = db.query(NudgeDispatch).filter_by(
            family_member_id=andrew.id
        ).count()
        assert count == 0
```

- [ ] **Step 5: Run the end-to-end class**

Run:
```bash
cd backend && pytest tests/test_nudges.py::TestEndToEndTick -v
```
Expected: both tests PASS.

- [ ] **Step 6: Run the full `test_nudges.py` file and the wider suite sanity check**

Run:
```bash
cd backend && pytest tests/test_nudges.py -v
```
Expected: all tests PASS (count should be at least 22 across all classes).

Run:
```bash
cd backend && pytest -x --ignore=tests/test_nudges.py -q
```
Expected: no regressions in the existing suite (PASS for all collected tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/scheduler.py backend/tests/test_nudges.py
git commit -m "backend: wire nudge_scan into the scheduler tick + e2e tests

Runs alongside morning_brief and anomaly_scan on the existing 5-min
tick. Exceptions are caught per-ticker so one failure doesn't
poison the rest. End-to-end tests cover scanner->gate->dispatch
through the single run_nudge_scan entry point and confirm the
quiet-proactivity path suppresses output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — Arch-check pass + handoff + open PR

**Files:**
- Create: `docs/handoffs/2026-04-21_sprint_05_phase_1_nudges.md`

- [ ] **Step 1: Run the architecture check and record the baseline**

Run:
```bash
node scripts/architecture-check.js
```
Expected: WARN count does not increase from the main baseline. Record the exact before/after counts in the handoff. If a new WARN appears, fix it before proceeding (most commonly: a new route missing `require_permission` — but Phase 1 adds no routes, so this shouldn't fire).

- [ ] **Step 2: Write the handoff**

Create `docs/handoffs/2026-04-21_sprint_05_phase_1_nudges.md`:

```markdown
# Sprint 05 Phase 1 — Core Nudge Engine — handoff

**Prepared:** 2026-04-21
**Branch:** `sprint/sprint-05-phase-1-nudges`
**Base:** `main @ {latest-main-sha}`

## What shipped

### Schema (migration 049)
- `scout.nudge_dispatches` with UNIQUE (dedupe_key) for idempotency
- Permission key `nudges.view_own` granted to all user tiers

### Backend
- `backend/app/models/nudges.py` — NudgeDispatch model
- `backend/app/services/nudges_service.py` — three scanners, proactivity gate, dispatch, entry point `run_nudge_scan`
- `backend/app/scheduler.py` — wires `_run_nudge_scan` into the existing 5-min tick

### Tests
- 22+ tests in `backend/tests/test_nudges.py` covering each scanner's happy + negative paths, apply_proactivity gates, dispatch + dedupe + push fan-out, and end-to-end.

## What this phase does NOT do

- `/api/nudges/me` — ships in Phase 2 alongside the frontend Recent-nudges card.
- Smoke spec — ships in Phase 2 alongside the API.
- Quiet hours — Phase 2.
- Digest batching — Phase 2.
- AI-composed copy — Phase 3.
- Admin rule engine — Phase 4.
- AI-driven discovery — Phase 5.

## Arch check

- Before: {N} WARNs
- After: {N} WARNs
- Delta from this branch: 0 expected (no routes, no new mutation endpoints)

## On Andrew's plate

- [ ] Review the Phase 1 PR
- [ ] Merge (squash)
- [ ] Apply migration 049 on Railway via the public proxy pattern
- [ ] Verify Railway + Vercel deploys
- [ ] Pull main + delete the phase branch

## Known follow-ups flagged during execution

- Phase 2 introduces the first user-facing surface for nudges; dogfood then.
- Dedupe key uses the proposal's `scheduled_for.date()` which is UTC — for family members in non-UTC timezones, this can create edge cases around midnight. Acceptable for Phase 1 (dedupe is best-effort prevention, not a correctness invariant); Phase 2 will add timezone-aware batching.
- Phase 2 will also introduce `quiet_hours.manage` permission and the per-family row on `quiet_hours_family`.
```

Fill `{latest-main-sha}` and the arch-check `{N}` counts before committing.

- [ ] **Step 3: Open the PR**

Run:
```bash
gh pr create --title "Sprint 05 Phase 1: Core nudge engine (migration 049)" --body "$(cat <<'EOF'
## Summary

Ships the core proactive-nudges engine behind Sprint 04 Phase 2's `proactivity` setting. Three built-in trigger scanners (overdue_task, upcoming_event, missed_routine), proactivity gate (quiet / balanced / forthcoming), dispatch sink that writes to `parent_action_items` and calls `push_service.send_push` when an active device exists. Idempotent via UNIQUE `dedupe_key`.

Wired into the existing APScheduler 5-min tick alongside `morning_brief` and `anomaly_scan`.

## Scope

This is **Phase 1 of 5** per `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md`. Out of scope for this PR (ships in later phases):

- Phase 2: quiet hours, digest batching, `/api/nudges/me`, smoke spec, Recent-nudges UI
- Phase 3: AI-composed per-member copy
- Phase 4: admin rule engine
- Phase 5: AI-driven trigger discovery

## Test plan

- [ ] `pytest backend/tests/test_nudges.py -v` — all 22+ tests pass
- [ ] `pytest -x backend/tests/ -q` — no regressions in the existing suite
- [ ] `node scripts/architecture-check.js` — WARN count unchanged
- [ ] Post-merge: migration 049 applied on Railway via public proxy pattern; `scout.nudge_dispatches` exists; `nudges.view_own` permission registered
- [ ] Railway `/health` returns `{"status":"ok"}` post-merge
- [ ] Vercel deploy green (no frontend changes; Vercel should build unchanged)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Note: the branch name should be `sprint/sprint-05-phase-1-nudges`. If it isn't already, create and push it first:

```bash
git checkout -b sprint/sprint-05-phase-1-nudges
git push -u origin sprint/sprint-05-phase-1-nudges
```

- [ ] **Step 4: Final sanity check + commit handoff**

```bash
git add docs/handoffs/2026-04-21_sprint_05_phase_1_nudges.md
git commit -m "docs: Sprint 05 Phase 1 handoff

Summary of shipped work: schema + model + service (3 scanners +
proactivity gate + dispatch with dedupe + Inbox + push fan-out) +
scheduler wiring. 22+ tests. Phase 1 adds no routes and no
frontend; Phase 2 adds the API + UI.

Records the arch-check before/after delta (zero new WARNs expected)
and the followups flagged during execution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

---

## Self-review checklist

Before declaring Phase 1 complete, verify:

- Migration 049 file exists in BOTH `backend/migrations/` and `database/migrations/` and is byte-identical.
- Every new mutating code path has at least one test. (Phase 1 has one mutating code path — `dispatch()` — covered by 4 tests.)
- `_run_nudge_scan` is wired into the existing `_tick` function, not into a new scheduler entry point.
- No new WARN in arch-check.
- No frontend files modified.
- Scheduler import of `nudges_service` is at module-level (not inside the tick function), to keep tick overhead low.
- `dispatch()` catches push errors — a down push provider must not poison the tick.

---

## Out of scope for Phase 1 (explicit)

Do NOT absorb these into the Phase 1 PR. Each has its own phase:

- `/api/nudges/me` route → Phase 2
- `scout.quiet_hours_family` table → Phase 2
- Digest batching in `dispatch` → Phase 2
- AI-composed nudge copy → Phase 3
- `scout.nudge_rules` table + admin CRUD → Phase 4
- `nudge_ai_discovery.py` + hourly scheduler job → Phase 5
- Smoke spec at `smoke-tests/tests/nudges.spec.ts` → Phase 2 (needs the API)
