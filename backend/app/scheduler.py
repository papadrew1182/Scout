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
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.foundation import Family, FamilyMember
from app.models.scheduled import ScheduledRun
from app.models.tier5 import AnomalySuppression

logger = logging.getLogger("scout.scheduler")

MORNING_BRIEF_HOUR = int(os.environ.get("SCOUT_MORNING_BRIEF_HOUR", "6"))
# Tier 4 anomaly scan — local-time hour (late evening, after the
# digest hour, so the day's activity is fully ingested).
ANOMALY_SCAN_HOUR = int(os.environ.get("SCOUT_ANOMALY_SCAN_HOUR", "21"))
# Friday evening retro — Python weekday() is 0=Mon..6=Sun, so 4=Fri.
WEEKLY_RETRO_WEEKDAY = int(os.environ.get("SCOUT_WEEKLY_RETRO_WEEKDAY", "4"))
WEEKLY_RETRO_HOUR = int(os.environ.get("SCOUT_WEEKLY_RETRO_HOUR", "18"))
# Daily moderation digest — evening local time, after most kid chat
# activity has settled. Dedupe key is (family_id, local_date).
MODERATION_DIGEST_HOUR = int(os.environ.get("SCOUT_MODERATION_DIGEST_HOUR", "20"))
# Skip the digest unless at least this many moderation_alert rows
# landed today. 0 or 1 events don't need a rollup — the live alerts
# already surface in the inbox.
MODERATION_DIGEST_MIN_EVENTS = int(
    os.environ.get("SCOUT_MODERATION_DIGEST_MIN_EVENTS", "2")
)
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

    Tier 5 F18 — multi-instance HA: wraps the whole tick in a
    Postgres advisory lock. If two app instances tick at the same
    time, only one acquires the lock and runs the jobs; the other
    returns immediately. ``pg_try_advisory_lock`` is session-scoped,
    so we acquire it on a dedicated connection, hold it for the
    length of the tick, and release on exit. This relies purely on
    Postgres — no new infrastructure.

    The production path wraps each job in its own commit/rollback
    boundary so one family's failure doesn't poison the next.
    Failures are logged; the scheduler thread stays alive.
    """
    now_utc = datetime.now(pytz.UTC)

    # Advisory lock acquired on its own short-lived connection.
    # Released no matter what via the finally block. Non-blocking
    # try — losing the lock race is not an error, just a no-op.
    from app.config import settings
    from app.database import engine

    lock_conn = engine.connect()
    try:
        lock_key = int(settings.scheduler_advisory_lock_key)
        got = lock_conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"),
            {"k": lock_key},
        ).scalar()
        if not got:
            logger.info("scheduler_tick_lock_contended key=%s", lock_key)
            return

        try:
            db = db_factory()
            try:
                run_morning_brief_tick(db, now_utc=now_utc)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("morning_brief_tick_failed: %s", e)
            finally:
                db.close()

            db = db_factory()
            try:
                run_weekly_retro_tick(db, now_utc=now_utc)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("weekly_retro_tick_failed: %s", e)
            finally:
                db.close()

            db = db_factory()
            try:
                run_moderation_digest_tick(db, now_utc=now_utc)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("moderation_digest_tick_failed: %s", e)
            finally:
                db.close()

            db = db_factory()
            try:
                run_anomaly_scan_tick(db, now_utc=now_utc)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("anomaly_scan_tick_failed: %s", e)
            finally:
                db.close()
        finally:
            # Release the advisory lock on the SAME connection we
            # acquired it on — advisory locks are session-scoped.
            try:
                lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:k)"),
                    {"k": int(settings.scheduler_advisory_lock_key)},
                )
            except Exception:
                pass
    finally:
        lock_conn.close()


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


# ---------------------------------------------------------------------------
# Weekly retro
# ---------------------------------------------------------------------------


def run_weekly_retro_tick(db: Session, *, now_utc: datetime) -> list[dict]:
    """For each family, if today is the configured retro weekday AND the
    local hour matches the configured retro hour, generate a weekly
    retro for the just-completed week. Dedupe by week_monday so the
    job fires exactly once per family per week regardless of how many
    ticks it sees during the target hour."""
    results: list[dict] = []

    families = list(db.scalars(select(Family)).all())
    for fam in families:
        try:
            tz = pytz.timezone(fam.timezone or "UTC")
        except Exception:
            tz = pytz.UTC
        local = now_utc.astimezone(tz)
        if local.weekday() != WEEKLY_RETRO_WEEKDAY:
            continue
        if local.hour != WEEKLY_RETRO_HOUR:
            continue
        if local.minute >= TICK_INTERVAL_MINUTES:
            continue

        # The retro is for the CURRENT week (Monday..today inclusive).
        week_monday = (local - timedelta(days=local.weekday())).date()
        out = run_weekly_retro_for_family(
            db, family_id=fam.id, week_start=week_monday
        )
        results.append(out)
    return results


def run_weekly_retro_for_family(
    db: Session, *, family_id, week_start: date
) -> dict:
    """Generate one weekly retro for one family. Dedupe-safe via
    scout_scheduled_runs (member_id NULL, run_date=week_start).

    Transaction-neutral: caller owns commit. Follows the same
    savepoint-for-dedupe pattern as morning brief."""
    from app.ai import orchestrator
    start_ts = datetime.now(pytz.UTC)

    try:
        with db.begin_nested():
            mutex = ScheduledRun(
                job_name="weekly_retro",
                family_id=family_id,
                member_id=None,
                run_date=week_start,
                status="success",
            )
            db.add(mutex)
            db.flush()
    except IntegrityError:
        return {
            "family_id": str(family_id),
            "week_start": week_start.isoformat(),
            "status": "skipped",
            "reason": "already_ran_this_week",
        }

    try:
        # Build the data bundle from existing persisted state. This is
        # the SAME data a parent could see in the app — the retro
        # doesn't invent facts.
        from app.ai.retro import build_retro_context, generate_retro_narrative

        context = build_retro_context(db, family_id=family_id, week_start=week_start)
        narrative = generate_retro_narrative(context)

        title = f"Week of {week_start.isoformat()} retro"
        action = ParentActionItem(
            family_id=family_id,
            # Retro is for the whole family — attribute to an arbitrary
            # adult so created_by is non-null. Pick the first active
            # adult we find.
            created_by_member_id=_first_adult_id(db, family_id),
            action_type="weekly_retro",
            title=title,
            detail=narrative,
            entity_type="weekly_retro",
            entity_id=None,
        )
        db.add(action)
        db.flush()

        mutex.duration_ms = int(
            (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
        )
        mutex.result = {
            "action_item_id": str(action.id),
            "narrative_length": len(narrative),
        }
        db.flush()
        logger.info(
            "weekly_retro_ok family=%s week=%s",
            family_id, week_start,
        )
        return {
            "family_id": str(family_id),
            "week_start": week_start.isoformat(),
            "status": "success",
            "action_item_id": str(action.id),
        }
    except Exception as e:
        try:
            mutex.status = "error"
            mutex.error = str(e)[:500]
            mutex.duration_ms = int(
                (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
            )
            db.flush()
        except Exception:
            pass
        logger.error(
            "weekly_retro_fail family=%s week=%s: %s",
            family_id, week_start, str(e)[:200],
        )
        return {
            "family_id": str(family_id),
            "week_start": week_start.isoformat(),
            "status": "error",
            "error": str(e)[:200],
        }


def _first_adult_id(db: Session, family_id):
    """Return any active adult member id for a family, or None. Used
    purely for created_by_member_id on family-scoped action items where
    no single member "owns" the item (retro, anomaly alert, etc.)."""
    row = db.scalars(
        select(FamilyMember)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.role == "adult")
        .where(FamilyMember.is_active.is_(True))
        .limit(1)
    ).first()
    return row.id if row else None


# ---------------------------------------------------------------------------
# Daily moderation digest
# ---------------------------------------------------------------------------

import re

_MODERATION_CATEGORY_RE = re.compile(r"\(([^)]+)\)\s*$")


def run_moderation_digest_tick(db: Session, *, now_utc: datetime) -> list[dict]:
    """For each family, if the local clock is inside the
    MODERATION_DIGEST_HOUR window, roll up the day's moderation_alert
    action items into a single `moderation_digest` row.

    The digest is a summary — no raw blocked content is included in
    the detail text. Parents who want to see the full context tap the
    individual live alerts (which still exist independently).

    Dedupe: (job_name='moderation_digest', family_id, member_id=NULL,
    run_date=local_date). The mutex inserts first, so skipped
    zero/one-event days don't spin back up on the next tick."""
    results: list[dict] = []
    families = list(db.scalars(select(Family)).all())
    for fam in families:
        try:
            tz = pytz.timezone(fam.timezone or "UTC")
        except Exception:
            tz = pytz.UTC
        local = now_utc.astimezone(tz)
        if local.hour != MODERATION_DIGEST_HOUR:
            continue
        if local.minute >= TICK_INTERVAL_MINUTES:
            continue
        run_date = local.date()
        out = run_moderation_digest_for_family(
            db, family_id=fam.id, run_date=run_date, tz=tz
        )
        results.append(out)
    return results


def run_moderation_digest_for_family(
    db: Session,
    *,
    family_id,
    run_date: date,
    tz: pytz.BaseTzInfo | None = None,
) -> dict:
    """Generate the daily moderation digest for one family.

    Transaction-neutral: caller owns commit. Follows the same
    savepoint-for-dedupe pattern as morning brief + weekly retro.
    Skips entirely (still consuming the mutex) when fewer than
    MODERATION_DIGEST_MIN_EVENTS alerts landed on this local day —
    live alerts already surface in the inbox for small counts."""
    start_ts = datetime.now(pytz.UTC)

    try:
        with db.begin_nested():
            mutex = ScheduledRun(
                job_name="moderation_digest",
                family_id=family_id,
                member_id=None,
                run_date=run_date,
                status="success",
            )
            db.add(mutex)
            db.flush()
    except IntegrityError:
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "skipped",
            "reason": "already_ran_today",
        }

    # Window is the local calendar day. Alerts are timestamped UTC,
    # so we compute UTC bounds from the local-day bounds.
    tzinfo = tz or pytz.UTC
    day_start_local = tzinfo.localize(
        datetime.combine(run_date, datetime.min.time())
    )
    day_end_local = day_start_local + timedelta(days=1)
    day_start_utc = day_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
    day_end_utc = day_end_local.astimezone(pytz.UTC).replace(tzinfo=None)

    alerts = list(
        db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family_id)
            .where(ParentActionItem.action_type == "moderation_alert")
            .where(ParentActionItem.created_at >= day_start_utc)
            .where(ParentActionItem.created_at < day_end_utc)
            .order_by(ParentActionItem.created_at.asc())
        ).all()
    )

    if len(alerts) < MODERATION_DIGEST_MIN_EVENTS:
        mutex.status = "success"
        mutex.result = {"event_count": len(alerts), "created_digest": False}
        mutex.duration_ms = int(
            (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
        )
        db.flush()
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "success",
            "created_digest": False,
            "event_count": len(alerts),
        }

    try:
        # Aggregate by child (created_by_member_id) + category.
        by_child: dict = {}
        child_names: dict = {}
        for a in alerts:
            bucket = by_child.setdefault(
                a.created_by_member_id,
                {"count": 0, "categories": {}, "times": []},
            )
            bucket["count"] += 1
            category = _extract_category(a.title)
            bucket["categories"][category] = bucket["categories"].get(category, 0) + 1
            # Render local time for the summary line.
            local_time = a.created_at.replace(tzinfo=pytz.UTC).astimezone(tzinfo)
            bucket["times"].append(_format_12h(local_time))

        # Resolve child first names in one query.
        members = list(
            db.scalars(
                select(FamilyMember).where(
                    FamilyMember.id.in_(list(by_child.keys()))
                )
            ).all()
        )
        for m in members:
            child_names[m.id] = m.first_name

        # Render a privacy-safe digest. No raw blocked text — only
        # counts, categories, and timestamps.
        lines: list[str] = [
            f"Scout blocked {len(alerts)} messages from your children today.",
            "",
        ]
        for child_id, bucket in by_child.items():
            name = child_names.get(child_id, "A child")
            cat_line = ", ".join(
                f"{cat}: {cnt}" for cat, cnt in sorted(bucket["categories"].items())
            )
            lines.append(
                f"- {name}: {bucket['count']} block{'s' if bucket['count'] != 1 else ''} ({cat_line})"
            )
            if bucket["times"]:
                lines.append("    times: " + ", ".join(bucket["times"]))
        lines.extend(
            [
                "",
                "Original blocked text is not shown here. Tap individual alerts in the inbox if you want more context, or open Settings → Scout AI to adjust how Scout handles these topics.",
            ]
        )
        detail = "\n".join(lines)

        digest = ParentActionItem(
            family_id=family_id,
            created_by_member_id=_first_adult_id(db, family_id),
            action_type="moderation_digest",
            title=f"{len(alerts)} moderation alerts today",
            detail=detail,
            entity_type="moderation_digest",
            entity_id=None,
        )
        db.add(digest)
        db.flush()

        mutex.duration_ms = int(
            (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
        )
        mutex.result = {
            "action_item_id": str(digest.id),
            "event_count": len(alerts),
            "created_digest": True,
        }
        db.flush()
        logger.info(
            "moderation_digest_ok family=%s date=%s events=%s",
            family_id, run_date, len(alerts),
        )
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "success",
            "created_digest": True,
            "event_count": len(alerts),
            "action_item_id": str(digest.id),
        }
    except Exception as e:
        try:
            mutex.status = "error"
            mutex.error = str(e)[:500]
            mutex.duration_ms = int(
                (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
            )
            db.flush()
        except Exception:
            pass
        logger.error(
            "moderation_digest_fail family=%s date=%s: %s",
            family_id, run_date, str(e)[:200],
        )
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "error",
            "error": str(e)[:200],
        }


def _format_12h(dt: datetime) -> str:
    """Cross-platform 12-hour clock formatter. %-I isn't available on
    Windows and %#I isn't on Linux, so we strip the leading zero
    manually after a plain %I:%M %p."""
    s = dt.strftime("%I:%M %p")
    if s.startswith("0"):
        s = s[1:]
    return s


# ---------------------------------------------------------------------------
# Daily anomaly scan (Tier 4 Feature 13)
# ---------------------------------------------------------------------------


def run_anomaly_scan_tick(db: Session, *, now_utc: datetime) -> list[dict]:
    """For each family, if local time is inside the ANOMALY_SCAN_HOUR
    window, run the deterministic detectors + AI narration and emit
    parent_action_items of action_type='anomaly_alert'. Dedupe via
    scout_scheduled_runs (job_name='anomaly_scan', run_date=local_date)."""
    results: list[dict] = []
    families = list(db.scalars(select(Family)).all())
    for fam in families:
        try:
            tz = pytz.timezone(fam.timezone or "UTC")
        except Exception:
            tz = pytz.UTC
        local = now_utc.astimezone(tz)
        if local.hour != ANOMALY_SCAN_HOUR:
            continue
        if local.minute >= TICK_INTERVAL_MINUTES:
            continue
        run_date = local.date()
        out = run_anomaly_scan_for_family(
            db, family_id=fam.id, run_date=run_date
        )
        results.append(out)
    return results


def run_anomaly_scan_for_family(
    db: Session, *, family_id, run_date: date
) -> dict:
    """Generate anomaly candidates for one family, narrate the top N,
    and write them as parent_action_items. Dedupe-safe; transaction
    neutral — caller owns commit."""
    start_ts = datetime.now(pytz.UTC)
    try:
        with db.begin_nested():
            mutex = ScheduledRun(
                job_name="anomaly_scan",
                family_id=family_id,
                member_id=None,
                run_date=run_date,
                status="success",
            )
            db.add(mutex)
            db.flush()
    except IntegrityError:
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "skipped",
            "reason": "already_ran_today",
        }

    try:
        from app.ai.anomalies import (
            generate_anomaly_candidates,
            narrate_candidate,
        )

        candidates = generate_anomaly_candidates(
            db, family_id=family_id, as_of=run_date
        )
        # Tier 5 F18 — suppression: filter candidates that are still
        # inside their configured quiet window, and refresh suppression
        # rows for anything we do emit so repeats stay quiet.
        from app.config import settings as _settings

        suppress_days = int(_settings.anomaly_suppression_days)
        # suppress_until lives in a timestamptz column, so both sides
        # of the comparison must be tz-aware. Keep UTC tzinfo
        # attached throughout.
        now_ts = datetime.now(pytz.UTC)
        suppress_until = now_ts + timedelta(days=suppress_days)

        allowed: list = []
        suppressed_count = 0
        for cand in candidates:
            existing = db.scalars(
                select(AnomalySuppression)
                .where(AnomalySuppression.family_id == family_id)
                .where(AnomalySuppression.anomaly_type == cand.anomaly_type)
                .where(AnomalySuppression.signature == cand.signature)
            ).first()

            if existing is not None and existing.suppress_until > now_ts:
                # Still in the quiet window — bump last_seen_at so
                # we can reason about repeat activity later, but
                # don't create an action_item.
                existing.last_seen_at = now_ts
                db.flush()
                suppressed_count += 1
                continue

            # Either never seen before or the quiet window elapsed.
            # Refresh or insert the suppression row with a new
            # suppress_until and let the candidate through.
            if existing is None:
                db.add(
                    AnomalySuppression(
                        family_id=family_id,
                        anomaly_type=cand.anomaly_type,
                        signature=cand.signature,
                        first_seen_at=now_ts,
                        last_seen_at=now_ts,
                        suppress_until=suppress_until,
                    )
                )
            else:
                existing.last_seen_at = now_ts
                existing.suppress_until = suppress_until
            db.flush()
            allowed.append(cand)

        created_count = 0
        for cand in allowed:
            narrative, model_used = narrate_candidate(cand)
            title = f"Scout noticed: {cand.anomaly_type.replace('_', ' ')}"
            item = ParentActionItem(
                family_id=family_id,
                created_by_member_id=_first_adult_id(db, family_id),
                action_type="anomaly_alert",
                title=title,
                detail=narrative,
                entity_type="anomaly",
                entity_id=None,
            )
            db.add(item)
            db.flush()
            created_count += 1

        mutex.duration_ms = int(
            (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
        )
        mutex.result = {
            "candidates": len(candidates),
            "suppressed": suppressed_count,
            "created": created_count,
        }
        db.flush()
        logger.info(
            "anomaly_scan_ok family=%s date=%s candidates=%s suppressed=%s created=%s",
            family_id, run_date, len(candidates), suppressed_count, created_count,
        )
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "success",
            "candidates": len(candidates),
            "suppressed": suppressed_count,
            "created": created_count,
        }
    except Exception as e:
        try:
            mutex.status = "error"
            mutex.error = str(e)[:500]
            mutex.duration_ms = int(
                (datetime.now(pytz.UTC) - start_ts).total_seconds() * 1000
            )
            db.flush()
        except Exception:
            pass
        logger.error(
            "anomaly_scan_fail family=%s date=%s: %s",
            family_id, run_date, str(e)[:200],
        )
        return {
            "family_id": str(family_id),
            "run_date": run_date.isoformat(),
            "status": "error",
            "error": str(e)[:200],
        }


def _extract_category(title: str) -> str:
    """Parse the bracketed category from a moderation_alert title like
    'Scout blocked a sensitive message (profanity)'. Returns 'unknown'
    when the pattern doesn't match — never raises."""
    if not title:
        return "unknown"
    m = _MODERATION_CATEGORY_RE.search(title)
    return (m.group(1) if m else "unknown") or "unknown"
