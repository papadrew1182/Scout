"""Scheduled background jobs for Scout proactive features.

This module owns the single in-process scheduler that runs alongside
the FastAPI app. Jobs:
  - morning_brief: runs at 6 AM local time per adult per family, once
    per day, generates a daily brief via the existing AI orchestrator,
    and drops it into parent_action_items as a 'daily_brief' row.

Design notes
------------
- **Dedupe is DB-side, not scheduler-side.** Every job INSERTs a row
  into `scout_scheduled_runs` with a unique (job_name, family_id,
  member_id, run_date) key BEFORE running. Re-runs hit the unique
  constraint and are skipped. This makes the scheduler multi-instance
  safe (even though Scout is currently single-instance) and idempotent
  against loose timing.
- **Timezone-awareness.** The scheduler tick happens every 5 minutes
  in whatever timezone the host runs in. Each family has a `timezone`
  column; the tick checks each family's local clock against the job's
  target hour. A family in a different TZ will fire correctly.
- **Testability.** Job functions are plain callables that take a
  session and the current datetime, so tests can invoke them directly
  with a controlled `now` without touching APScheduler.
- **Graceful skip in tests.** `start_scheduler()` is only called from
  the FastAPI lifespan hook. Pytest imports the app module but
  conftest.py uses a different session/bootstrap path that never runs
  the lifespan, so the scheduler never starts during unit tests.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Callable

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.foundation import Family, FamilyMember
from app.models.scheduled import ScheduledRun

logger = logging.getLogger("scout.scheduler")

MORNING_BRIEF_HOUR = int(os.environ.get("SCOUT_MORNING_BRIEF_HOUR", "6"))
TICK_INTERVAL_MINUTES = int(os.environ.get("SCOUT_SCHEDULER_TICK_MINUTES", "5"))

_scheduler: BackgroundScheduler | None = None


def start_scheduler(db_factory: Callable[[], Session]) -> BackgroundScheduler:
    """Start the in-process APScheduler. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(daemon=True, timezone=pytz.UTC)
    scheduler.add_job(
        _tick,
        "interval",
        minutes=TICK_INTERVAL_MINUTES,
        args=[db_factory],
        id="scout_tick",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "scheduler_started tick_minutes=%s morning_brief_hour=%s",
        TICK_INTERVAL_MINUTES, MORNING_BRIEF_HOUR,
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _tick(db_factory: Callable[[], Session]) -> None:
    """Scheduler tick: one pass over all families + jobs.

    The production path wraps each ``run_morning_brief_tick`` in a
    commit/rollback boundary so one family's failure doesn't poison
    the next. Failures are logged; the scheduler thread stays alive.
    """
    now_utc = datetime.now(pytz.UTC)
    db = db_factory()
    try:
        run_morning_brief_tick(db, now_utc=now_utc)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("scheduler_tick_failed: %s", e)
    finally:
        db.close()


def run_morning_brief_tick(
    db: Session,
    *,
    now_utc: datetime,
) -> list[dict]:
    """For each family, if the family's local clock is within the
    MORNING_BRIEF_HOUR window, generate a brief for each adult that
    hasn't already received one today.

    The "window" is [HOUR:00, HOUR:TICK_INTERVAL_MINUTES) — a single
    tick fires the job. Dedupe via scout_scheduled_runs unique key
    protects against overlap with the next tick and multi-instance.

    Returns a list of dicts describing what happened, for test
    assertions and structured logging.
    """
    results: list[dict] = []

    families = list(db.scalars(select(Family)).all())
    for fam in families:
        try:
            tz = pytz.timezone(fam.timezone or "UTC")
        except Exception:
            tz = pytz.UTC
        local = now_utc.astimezone(tz)
        if local.hour != MORNING_BRIEF_HOUR:
            continue
        if local.minute >= TICK_INTERVAL_MINUTES:
            # Already past the first tick of the hour; next hour's run
            # will happen tomorrow. Dedupe will skip repeats anyway.
            continue

        run_date = local.date()
        adults = list(db.scalars(
            select(FamilyMember)
            .where(FamilyMember.family_id == fam.id)
            .where(FamilyMember.role == "adult")
            .where(FamilyMember.is_active.is_(True))
        ).all())

        for adult in adults:
            outcome = run_morning_brief_for_member(
                db, family_id=fam.id, member_id=adult.id, run_date=run_date
            )
            results.append(outcome)

    return results


def run_morning_brief_for_member(
    db: Session,
    *,
    family_id,
    member_id,
    run_date: date,
) -> dict:
    """Generate one morning brief for one adult and attach it as an
    Action Inbox item. Dedupe-safe via scout_scheduled_runs.

    The function is transaction-neutral: it adds + flushes rows but
    does NOT call ``db.commit()``. The caller owns commit boundaries
    so the same function works in the scheduler's production path
    (where ``_tick`` commits after each member) and in pytest (where
    the conftest fixture holds the outer transaction open and rolls
    back on teardown).

    Savepoints protect the dedupe insert: a unique-constraint failure
    on the mutex rolls back ONLY the savepoint, not the whole turn.
    """
    start = datetime.now(pytz.UTC)

    # Step 1 — savepointed dedupe insert.
    try:
        with db.begin_nested():
            mutex = ScheduledRun(
                job_name="morning_brief",
                family_id=family_id,
                member_id=member_id,
                run_date=run_date,
                status="success",
            )
            db.add(mutex)
            db.flush()
    except IntegrityError:
        return {
            "family_id": str(family_id),
            "member_id": str(member_id),
            "status": "skipped",
            "reason": "already_ran_today",
        }

    # Step 2 — generate the brief + create the Action Inbox item. If
    # the orchestrator call fails, overwrite the mutex's status inside
    # its own savepoint so we still have a durable error row that
    # prevents retry storms.
    try:
        from app.ai import orchestrator  # local import: circular-safe

        brief = orchestrator.generate_daily_brief(db, family_id, member_id)
        action = ParentActionItem(
            family_id=family_id,
            created_by_member_id=member_id,
            action_type="daily_brief",
            title="Morning brief ready",
            detail=brief.get("brief") or "",
            entity_type="ai_daily_insight",
            entity_id=None,
        )
        db.add(action)
        db.flush()

        mutex.duration_ms = int((datetime.now(pytz.UTC) - start).total_seconds() * 1000)
        mutex.result = {
            "action_item_id": str(action.id),
            "model": brief.get("model"),
            "brief_length": len(brief.get("brief") or ""),
        }
        db.flush()
        logger.info(
            "morning_brief_ok family=%s member=%s date=%s model=%s",
            family_id, member_id, run_date, brief.get("model"),
        )
        return {
            "family_id": str(family_id),
            "member_id": str(member_id),
            "status": "success",
            "action_item_id": str(action.id),
            "model": brief.get("model"),
        }
    except Exception as e:
        # Mark the mutex row as error in-place. It's still attached to
        # the session, so no additional INSERT is needed — just mutate
        # and flush.
        try:
            mutex.status = "error"
            mutex.error = str(e)[:500]
            mutex.duration_ms = int((datetime.now(pytz.UTC) - start).total_seconds() * 1000)
            db.flush()
        except Exception:
            pass
        logger.error(
            "morning_brief_fail family=%s member=%s: %s",
            family_id, member_id, str(e)[:200],
        )
        return {
            "family_id": str(family_id),
            "member_id": str(member_id),
            "status": "error",
            "error": str(e)[:200],
        }
