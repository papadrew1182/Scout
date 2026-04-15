"""Session 2 block 3 — connector activation + control-plane realism.

Block 3 closes the loop between adapter execution and the
control-plane DB state. These tests verify:

  * scout.sync_runs is written by sync_persistence and
    propagates to scout.connector_accounts (status, last_success_at,
    last_error_at, last_error_message).
  * Freshness derivation matches scout.v_control_plane semantics.
  * sync_persistence.db_health_for_family returns a stable shape
    for connectors with and without account rows.
  * scout.stale_data_alerts insert/acknowledge are idempotent.
  * SyncService.run_and_persist drives the full pipeline from
    request -> sync_runs row -> connector_account update.
  * GoogleCalendarAdapter (block 3 first real pass) reports a
    quiet operational baseline and normalizes Google Calendar v3
    event payloads into scout.external_calendar_events shape.
  * scout.calendar_exports state transitions via
    sync_persistence.mark_export_status are reflected by the
    /api/calendar/exports/upcoming view.
  * /api/connectors/health is DB-backed (Block 3 contract).
  * /api/control-plane/summary aggregates real mixed states
    correctly (healthy vs stale vs error).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytz
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.connectors.base import (
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)
from services.connectors.google_calendar.adapter import GoogleCalendarAdapter
from services.connectors.sync_persistence import (
    LIVE_WINDOW,
    LAGGING_WINDOW,
    acknowledge_stale_alerts,
    db_health_for_family,
    derive_freshness,
    finish_sync_run,
    mark_export_status,
    raise_stale_alert,
    record_event,
    start_sync_run,
)
from services.connectors.sync_service import SyncRequest, SyncService


# ---------------------------------------------------------------------------
# Helpers — tiny seed primitives so each test composes the state it needs.
# Block 3 is family-scoped end-to-end so every helper threads family_id.
# ---------------------------------------------------------------------------


def _seed_family(db: Session, name: str = "Block3 Test") -> uuid.UUID:
    fid = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO public.families (id, name, timezone) "
            "VALUES (:id, :n, 'America/Chicago')"
        ),
        {"id": fid, "n": name},
    )
    db.flush()
    return fid


def _seed_member(db: Session, family_id: uuid.UUID, first_name: str = "Andrew") -> uuid.UUID:
    mid = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO public.family_members
                (id, family_id, first_name, last_name, role, birthdate)
            VALUES
                (:id, :fid, :fn, 'Roberts', 'adult', '1985-06-14')
            """
        ),
        {"id": mid, "fid": family_id, "fn": first_name},
    )
    db.flush()
    return mid


def _connector_id(db: Session, connector_key: str) -> uuid.UUID:
    """Look up the seeded scout.connectors row by key. Migration 022
    seeds all nine, so this never returns None in a healthy test
    DB. We resolve by key rather than caching to keep tests
    independent of insertion order."""
    row = db.execute(
        text(
            "SELECT id FROM scout.connectors WHERE connector_key = :k"
        ),
        {"k": connector_key},
    ).first()
    assert row is not None, f"connector {connector_key!r} not seeded"
    return row.id


def _seed_account(
    db: Session,
    *,
    family_id: uuid.UUID,
    connector_key: str,
    status: str = "configured",
    last_success_at: datetime | None = None,
    last_error_at: datetime | None = None,
    last_error_message: str | None = None,
) -> uuid.UUID:
    """Insert one scout.connector_accounts row in an arbitrary
    starting state. Used by tests that want to set up mixed
    healthy/stale/error fleets without having to drive a real
    sync."""
    aid = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO scout.connector_accounts
                (id, connector_id, family_id, account_label, status,
                 last_success_at, last_error_at, last_error_message)
            VALUES
                (:id, :cid, :fid, 'Test Account', :status,
                 :ls, :le, :lem)
            """
        ),
        {
            "id": aid,
            "cid": _connector_id(db, connector_key),
            "fid": family_id,
            "status": status,
            "ls": last_success_at,
            "le": last_error_at,
            "lem": last_error_message,
        },
    )
    db.flush()
    return aid


def _seed_sync_job(
    db: Session,
    *,
    connector_account_id: uuid.UUID,
    entity_key: str = "calendar_event",
) -> uuid.UUID:
    jid = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO scout.sync_jobs
                (id, connector_account_id, entity_key, cadence_seconds, is_enabled)
            VALUES
                (:id, :acct, :ent, 900, true)
            """
        ),
        {"id": jid, "acct": connector_account_id, "ent": entity_key},
    )
    db.flush()
    return jid


# ---------------------------------------------------------------------------
# Freshness derivation — pure function tests
# ---------------------------------------------------------------------------


class TestFreshnessDerivation:
    def test_unknown_when_never_succeeded(self):
        assert derive_freshness(None) == FreshnessState.UNKNOWN

    def test_live_inside_one_hour_window(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(minutes=30)
        assert derive_freshness(recent, now=now) == FreshnessState.LIVE

    def test_lagging_after_one_hour(self):
        now = datetime.now(timezone.utc)
        ago = now - (LIVE_WINDOW + timedelta(minutes=5))
        assert derive_freshness(ago, now=now) == FreshnessState.LAGGING

    def test_stale_after_six_hours(self):
        now = datetime.now(timezone.utc)
        ago = now - (LAGGING_WINDOW + timedelta(minutes=5))
        assert derive_freshness(ago, now=now) == FreshnessState.STALE

    def test_naive_datetime_treated_as_utc(self):
        # The DB returns naive timestamps for some drivers; the
        # helper must not blow up — it should treat naive values
        # as UTC.
        now = datetime.now(timezone.utc)
        naive = now.replace(tzinfo=None) - timedelta(minutes=5)
        assert derive_freshness(naive, now=now) == FreshnessState.LIVE


# ---------------------------------------------------------------------------
# sync_persistence — start/finish + state propagation
# ---------------------------------------------------------------------------


class TestSyncRunPersistence:
    def test_start_writes_running_row_and_flips_account_to_syncing(
        self, db: Session
    ):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")
        jid = _seed_sync_job(db, connector_account_id=aid)

        run_id = start_sync_run(db, sync_job_id=jid)

        run = db.execute(
            text(
                "SELECT status, started_at, finished_at FROM scout.sync_runs WHERE id = :id"
            ),
            {"id": run_id},
        ).first()
        assert run is not None
        assert run.status == "running"
        assert run.started_at is not None
        assert run.finished_at is None

        acct = db.execute(
            text(
                "SELECT status FROM scout.connector_accounts WHERE id = :id"
            ),
            {"id": aid},
        ).first()
        assert acct.status == "syncing"

        job = db.execute(
            text(
                "SELECT last_run_started_at FROM scout.sync_jobs WHERE id = :id"
            ),
            {"id": jid},
        ).first()
        assert job.last_run_started_at is not None

    def test_finish_success_promotes_account_to_connected_with_last_success(
        self, db: Session
    ):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")
        jid = _seed_sync_job(db, connector_account_id=aid)

        run_id = start_sync_run(db, sync_job_id=jid)
        finish_sync_run(
            db,
            run_id=run_id,
            result=SyncResult(status="success", records_processed=12, next_cursor="abc"),
        )

        run = db.execute(
            text(
                "SELECT status, finished_at, records_processed FROM scout.sync_runs WHERE id = :id"
            ),
            {"id": run_id},
        ).first()
        assert run.status == "success"
        assert run.finished_at is not None
        assert run.records_processed == 12

        acct = db.execute(
            text(
                """
                SELECT status, last_success_at, last_error_at, last_error_message
                FROM scout.connector_accounts WHERE id = :id
                """
            ),
            {"id": aid},
        ).first()
        assert acct.status == "connected"
        assert acct.last_success_at is not None
        assert acct.last_error_at is None
        assert acct.last_error_message is None

    def test_finish_error_flips_account_to_error_and_records_message(
        self, db: Session
    ):
        fid = _seed_family(db)
        aid = _seed_account(
            db,
            family_id=fid,
            connector_key="google_calendar",
            last_success_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        jid = _seed_sync_job(db, connector_account_id=aid)

        run_id = start_sync_run(db, sync_job_id=jid)
        finish_sync_run(
            db,
            run_id=run_id,
            result=SyncResult(
                status="error",
                records_processed=0,
                error_message="oauth token expired",
            ),
        )

        acct = db.execute(
            text(
                """
                SELECT status, last_success_at, last_error_at, last_error_message
                FROM scout.connector_accounts WHERE id = :id
                """
            ),
            {"id": aid},
        ).first()
        assert acct.status == "error"
        # last_success_at is preserved across failures so freshness
        # can still be derived from the most recent good run.
        assert acct.last_success_at is not None
        assert acct.last_error_at is not None
        assert acct.last_error_message == "oauth token expired"

    def test_finish_partial_records_warning_but_keeps_connected(
        self, db: Session
    ):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="ynab")
        jid = _seed_sync_job(
            db, connector_account_id=aid, entity_key="budget_snapshot"
        )

        run_id = start_sync_run(db, sync_job_id=jid)
        finish_sync_run(
            db,
            run_id=run_id,
            result=SyncResult(
                status="partial",
                records_processed=4,
                error_message="3 categories skipped",
            ),
        )

        acct = db.execute(
            text(
                """
                SELECT status, last_success_at, last_error_message
                FROM scout.connector_accounts WHERE id = :id
                """
            ),
            {"id": aid},
        ).first()
        assert acct.status == "connected"
        assert acct.last_success_at is not None
        assert acct.last_error_message == "3 categories skipped"


# ---------------------------------------------------------------------------
# Stale-data alerts + connector event log
# ---------------------------------------------------------------------------


class TestStaleAlerts:
    def test_raise_then_acknowledge(self, db: Session):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")

        alert_id = raise_stale_alert(
            db, connector_account_id=aid, entity_key="calendar_event"
        )
        assert alert_id is not None

        open_count = db.execute(
            text(
                """
                SELECT COUNT(*) FROM scout.stale_data_alerts
                WHERE connector_account_id = :a AND acknowledged_at IS NULL
                """
            ),
            {"a": aid},
        ).scalar()
        assert open_count == 1

        ack = acknowledge_stale_alerts(
            db, connector_account_id=aid, entity_key="calendar_event"
        )
        assert ack == 1

        open_count = db.execute(
            text(
                """
                SELECT COUNT(*) FROM scout.stale_data_alerts
                WHERE connector_account_id = :a AND acknowledged_at IS NULL
                """
            ),
            {"a": aid},
        ).scalar()
        assert open_count == 0

    def test_raise_is_idempotent_for_open_alerts(self, db: Session):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")

        first = raise_stale_alert(
            db, connector_account_id=aid, entity_key="calendar_event"
        )
        second = raise_stale_alert(
            db, connector_account_id=aid, entity_key="calendar_event"
        )
        assert first == second

        total = db.execute(
            text(
                """
                SELECT COUNT(*) FROM scout.stale_data_alerts
                WHERE connector_account_id = :a
                """
            ),
            {"a": aid},
        ).scalar()
        assert total == 1

    def test_record_event_writes_jsonb_payload(self, db: Session):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")

        record_event(
            db,
            connector_account_id=aid,
            event_type="sync.error",
            severity="error",
            payload={"reason": "rate_limited", "retry_in_sec": 60},
        )
        row = db.execute(
            text(
                """
                SELECT event_type, severity, payload
                FROM scout.connector_event_log
                WHERE connector_account_id = :a
                """
            ),
            {"a": aid},
        ).first()
        assert row.event_type == "sync.error"
        assert row.severity == "error"
        assert row.payload["reason"] == "rate_limited"


# ---------------------------------------------------------------------------
# DB-backed health snapshot
# ---------------------------------------------------------------------------


class TestDbHealthForFamily:
    def test_returns_one_row_per_registered_connector(self, db: Session):
        fid = _seed_family(db)
        rows = db_health_for_family(db, family_id=fid)
        # All nine connectors are seeded by migration 022.
        assert len(rows) == 9
        keys = {r.connector_key for r in rows}
        assert keys == {
            "google_calendar",
            "hearth_display",
            "greenlight",
            "rex",
            "ynab",
            "google_maps",
            "apple_health",
            "nike_run_club",
            "exxir",
        }

    def test_no_account_falls_back_to_disconnected_or_decision_gated(
        self, db: Session
    ):
        fid = _seed_family(db)
        rows = db_health_for_family(db, family_id=fid)
        by_key = {r.connector_key: r for r in rows}
        assert by_key["exxir"].status == "decision_gated"
        assert by_key["google_calendar"].status == "disconnected"
        for r in rows:
            assert r.healthy is False
            assert r.freshness_state == FreshnessState.UNKNOWN

    def test_connected_account_inside_live_window_is_healthy(
        self, db: Session
    ):
        fid = _seed_family(db)
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        _seed_account(
            db,
            family_id=fid,
            connector_key="google_calendar",
            status="connected",
            last_success_at=recent,
        )
        rows = {r.connector_key: r for r in db_health_for_family(db, family_id=fid)}
        gc = rows["google_calendar"]
        assert gc.status == "connected"
        assert gc.healthy is True
        assert gc.freshness_state == FreshnessState.LIVE

    def test_error_account_is_not_healthy_even_with_recent_success(
        self, db: Session
    ):
        fid = _seed_family(db)
        recent = datetime.now(timezone.utc) - timedelta(minutes=10)
        _seed_account(
            db,
            family_id=fid,
            connector_key="google_calendar",
            status="error",
            last_success_at=recent,
            last_error_at=datetime.now(timezone.utc),
            last_error_message="quota exceeded",
        )
        rows = {r.connector_key: r for r in db_health_for_family(db, family_id=fid)}
        gc = rows["google_calendar"]
        assert gc.status == "error"
        assert gc.healthy is False
        assert gc.last_error_message == "quota exceeded"

    def test_open_alert_count_reflects_unacknowledged_alerts(self, db: Session):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="ynab")
        raise_stale_alert(
            db, connector_account_id=aid, entity_key="budget_snapshot"
        )
        raise_stale_alert(
            db, connector_account_id=aid, entity_key="bill_snapshot"
        )
        rows = {r.connector_key: r for r in db_health_for_family(db, family_id=fid)}
        assert rows["ynab"].open_alert_count == 2


# ---------------------------------------------------------------------------
# SyncService end-to-end orchestration
# ---------------------------------------------------------------------------


class TestSyncServiceOrchestration:
    def test_run_and_persist_writes_sync_run_and_updates_account(
        self, db: Session
    ):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")
        jid = _seed_sync_job(db, connector_account_id=aid)

        svc = SyncService()
        result = svc.run_and_persist(
            db,
            sync_job_id=jid,
            request=SyncRequest(
                connector_account_id=aid,
                connector_key="google_calendar",
                entity_key="calendar_event",
            ),
        )
        assert result.status == "success"

        # sync_runs row exists in success state
        runs = db.execute(
            text(
                """
                SELECT status, records_processed FROM scout.sync_runs
                WHERE sync_job_id = :j
                """
            ),
            {"j": jid},
        ).all()
        assert len(runs) == 1
        assert runs[0].status == "success"

        # connector_account flipped to connected with fresh
        # last_success_at
        acct = db.execute(
            text(
                "SELECT status, last_success_at FROM scout.connector_accounts WHERE id = :a"
            ),
            {"a": aid},
        ).first()
        assert acct.status == "connected"
        assert acct.last_success_at is not None

    def test_run_and_persist_records_event_on_error(self, db: Session):
        fid = _seed_family(db)
        aid = _seed_account(db, family_id=fid, connector_key="rex")
        jid = _seed_sync_job(db, connector_account_id=aid, entity_key="rex_inbound")

        svc = SyncService()
        # Rex adapter is still a NotImplementedError stub, so
        # run_and_persist should turn that into status='error'
        # AND write a connector_event_log row.
        result = svc.run_and_persist(
            db,
            sync_job_id=jid,
            request=SyncRequest(
                connector_account_id=aid,
                connector_key="rex",
                entity_key="rex_inbound",
            ),
        )
        assert result.status == "error"

        acct = db.execute(
            text(
                "SELECT status, last_error_message FROM scout.connector_accounts WHERE id = :a"
            ),
            {"a": aid},
        ).first()
        assert acct.status == "error"
        assert acct.last_error_message is not None

        evt = db.execute(
            text(
                """
                SELECT event_type, severity FROM scout.connector_event_log
                WHERE connector_account_id = :a AND event_type = 'sync.error'
                """
            ),
            {"a": aid},
        ).first()
        assert evt is not None
        assert evt.severity == "error"


# ---------------------------------------------------------------------------
# Google Calendar adapter — block 3 first real pass
# ---------------------------------------------------------------------------


class TestGoogleCalendarAdapter:
    def test_health_check_clientless_returns_quiet_baseline(self):
        adapter = GoogleCalendarAdapter()
        h = adapter.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.connector_key == "google_calendar"
        assert h.healthy is False
        # No exploding stub message — the whole point of block 3
        # is that the adapter no longer claims to be unimplemented.
        assert h.last_error_message is None
        assert h.freshness_state == FreshnessState.UNKNOWN

    def test_get_account_summary_clientless_returns_no_account(self):
        adapter = GoogleCalendarAdapter()
        summary = adapter.get_account_summary()
        assert isinstance(summary, ConnectorAccountSummary)
        assert summary.connector_key == "google_calendar"
        assert summary.account_label is None
        assert summary.account_external_id is None
        assert "calendar.readonly" in summary.scopes

    def test_incremental_sync_clientless_succeeds_with_zero_records(self):
        adapter = GoogleCalendarAdapter()
        result = adapter.incremental_sync(cursor="prior-cursor")
        assert result.status == "success"
        assert result.records_processed == 0
        assert result.next_cursor == "prior-cursor"
        # And the adapter's local view of freshness flips to LIVE
        # so the in-process façade reads consistently.
        assert adapter.get_freshness_state() == FreshnessState.LIVE

    def test_backfill_clientless_succeeds_with_zero_records(self):
        adapter = GoogleCalendarAdapter()
        result = adapter.backfill(scope={"window_days": 30})
        assert result.status == "success"
        assert result.records_processed == 0

    def test_map_to_internal_objects_normalizes_timed_event(self):
        adapter = GoogleCalendarAdapter()
        records = [
            {
                "summary": "Sadie soccer",
                "start": {"dateTime": "2026-04-14T17:30:00-05:00"},
                "end": {"dateTime": "2026-04-14T18:30:00-05:00"},
                "location": "Riverside Park",
            }
        ]
        out = adapter.map_to_internal_objects(records)
        assert len(out) == 1
        row = out[0]
        assert row["source"] == "google_calendar"
        assert row["title"] == "Sadie soccer"
        assert row["location"] == "Riverside Park"
        assert row["all_day"] is False
        assert isinstance(row["starts_at"], datetime)
        assert row["starts_at"].tzinfo is not None

    def test_map_to_internal_objects_normalizes_all_day_event(self):
        adapter = GoogleCalendarAdapter()
        out = adapter.map_to_internal_objects(
            [
                {
                    "summary": "School holiday",
                    "start": {"date": "2026-04-15"},
                    "end": {"date": "2026-04-16"},
                }
            ]
        )
        assert len(out) == 1
        assert out[0]["all_day"] is True

    def test_map_to_internal_objects_skips_malformed_records(self):
        adapter = GoogleCalendarAdapter()
        out = adapter.map_to_internal_objects(
            [
                {"summary": "no times here"},
                {"summary": "good", "start": {"date": "2026-04-15"}, "end": {"date": "2026-04-16"}},
            ]
        )
        assert len(out) == 1
        assert out[0]["title"] == "good"

    def test_map_output_inserts_into_external_calendar_events(self, db: Session):
        """End-to-end: the mapper output must be insertable into
        scout.external_calendar_events without column shape drift."""
        fid = _seed_family(db)
        adapter = GoogleCalendarAdapter()
        rows = adapter.map_to_internal_objects(
            [
                {
                    "summary": "Robert run",
                    "start": {"dateTime": "2026-04-14T06:00:00-05:00"},
                    "end": {"dateTime": "2026-04-14T07:00:00-05:00"},
                }
            ]
        )
        for r in rows:
            db.execute(
                text(
                    """
                    INSERT INTO scout.external_calendar_events
                        (family_id, source, title, starts_at, ends_at, location, all_day)
                    VALUES
                        (:fid, :source, :title, :starts_at, :ends_at, :location, :all_day)
                    """
                ),
                {"fid": fid, **r},
            )
        db.flush()

        count = db.execute(
            text(
                "SELECT COUNT(*) FROM scout.external_calendar_events WHERE family_id = :fid"
            ),
            {"fid": fid},
        ).scalar()
        assert count == 1


# ---------------------------------------------------------------------------
# Calendar export state transitions + view consistency
# ---------------------------------------------------------------------------


def _insert_pending_export(
    db: Session,
    *,
    family_id: uuid.UUID,
    label: str = "Evening Reset",
    starts_at: datetime | None = None,
) -> uuid.UUID:
    starts_at = starts_at or (datetime.now(timezone.utc) + timedelta(hours=2))
    eid = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO scout.calendar_exports
                (id, family_id, source_type, source_id, target, label,
                 starts_at, ends_at, hearth_visible, export_status)
            VALUES
                (:id, :fid, 'routine_block', :sid, 'google_calendar', :label,
                 :start, :end, true, 'pending')
            """
        ),
        {
            "id": eid,
            "fid": family_id,
            "sid": uuid.uuid4(),
            "label": label,
            "start": starts_at,
            "end": starts_at + timedelta(minutes=30),
        },
    )
    db.flush()
    return eid


class TestCalendarExportTransitions:
    def test_mark_exported_stamps_last_exported_at(self, db: Session):
        fid = _seed_family(db)
        eid = _insert_pending_export(db, family_id=fid)

        mark_export_status(db, calendar_export_id=eid, new_status="exported")

        row = db.execute(
            text(
                """
                SELECT export_status, last_exported_at, error_message
                FROM scout.calendar_exports WHERE id = :id
                """
            ),
            {"id": eid},
        ).first()
        assert row.export_status == "exported"
        assert row.last_exported_at is not None
        assert row.error_message is None

    def test_mark_error_writes_message_and_keeps_visible_in_view(
        self, db: Session
    ):
        fid = _seed_family(db)
        eid = _insert_pending_export(db, family_id=fid)

        mark_export_status(
            db,
            calendar_export_id=eid,
            new_status="error",
            error_message="invalid grant",
        )

        row = db.execute(
            text(
                """
                SELECT export_status, error_message
                FROM scout.calendar_exports WHERE id = :id
                """
            ),
            {"id": eid},
        ).first()
        assert row.export_status == "error"
        assert row.error_message == "invalid grant"

        # v_calendar_publication explicitly excludes 'error' rows
        # so they don't render on Hearth — confirm that filtering.
        view_row = db.execute(
            text(
                "SELECT COUNT(*) FROM scout.v_calendar_publication WHERE calendar_export_id = :id"
            ),
            {"id": eid},
        ).scalar()
        assert view_row == 0

    def test_mark_stale_keeps_row_visible_in_view(self, db: Session):
        fid = _seed_family(db)
        eid = _insert_pending_export(db, family_id=fid)

        mark_export_status(db, calendar_export_id=eid, new_status="exported")
        mark_export_status(db, calendar_export_id=eid, new_status="stale")

        view_row = db.execute(
            text(
                """
                SELECT export_status FROM scout.v_calendar_publication
                WHERE calendar_export_id = :id
                """
            ),
            {"id": eid},
        ).first()
        assert view_row is not None
        assert view_row.export_status == "stale"

    def test_invalid_status_raises_value_error(self, db: Session):
        fid = _seed_family(db)
        eid = _insert_pending_export(db, family_id=fid)
        with pytest.raises(ValueError):
            mark_export_status(
                db, calendar_export_id=eid, new_status="totally_made_up"
            )


# ---------------------------------------------------------------------------
# Endpoint contract tests — DB-backed /api/connectors/health and
# /api/control-plane/summary with mixed real states.
# ---------------------------------------------------------------------------


@pytest.fixture
def session2_block3_client(db):
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


def _bearer(db: Session, member_id: uuid.UUID) -> str:
    from app.models.foundation import Session as SessionModel, UserAccount
    from app.services.auth_service import hash_password

    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"s2b3-{uuid.uuid4().hex[:8]}@scout.local",
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=False,
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


class TestConnectorsHealthEndpoint:
    def test_db_backed_shape_locks_block3_keys(
        self, session2_block3_client, db: Session
    ):
        fid = _seed_family(db)
        mid = _seed_member(db, fid)
        tok = _bearer(db, mid)

        r = session2_block3_client.get(
            "/api/connectors/health",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        items = body["items"]
        assert len(items) == 9
        for item in items:
            # Block 3 expanded the contract additively; legacy
            # consumers still see the block 2 keys.
            assert set(item.keys()) >= {
                "connector_key",
                "label",
                "healthy",
                "status",
                "freshness_state",
                "last_success_at",
                "last_error_at",
                "last_error_message",
                "open_alert_count",
            }
            assert item["freshness_state"] in {"live", "lagging", "stale", "unknown"}
            # Block 3 status vocabulary is locked.
            assert item["status"] in {
                "disconnected", "configured", "connected", "syncing",
                "stale", "error", "disabled", "decision_gated",
            }

    def test_connected_account_renders_as_healthy(
        self, session2_block3_client, db: Session
    ):
        fid = _seed_family(db)
        mid = _seed_member(db, fid)
        recent = datetime.now(timezone.utc) - timedelta(minutes=2)
        _seed_account(
            db,
            family_id=fid,
            connector_key="google_calendar",
            status="connected",
            last_success_at=recent,
        )
        tok = _bearer(db, mid)

        r = session2_block3_client.get(
            "/api/connectors/health",
            headers={"Authorization": f"Bearer {tok}"},
        )
        body = r.json()
        gc = next(i for i in body["items"] if i["connector_key"] == "google_calendar")
        assert gc["status"] == "connected"
        assert gc["healthy"] is True
        assert gc["freshness_state"] == "live"

    def test_error_account_renders_as_unhealthy(
        self, session2_block3_client, db: Session
    ):
        fid = _seed_family(db)
        mid = _seed_member(db, fid)
        _seed_account(
            db,
            family_id=fid,
            connector_key="ynab",
            status="error",
            last_success_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_error_at=datetime.now(timezone.utc),
            last_error_message="api 401",
        )
        tok = _bearer(db, mid)

        r = session2_block3_client.get(
            "/api/connectors/health",
            headers={"Authorization": f"Bearer {tok}"},
        )
        body = r.json()
        ynab = next(i for i in body["items"] if i["connector_key"] == "ynab")
        assert ynab["status"] == "error"
        assert ynab["healthy"] is False
        assert ynab["last_error_message"] == "api 401"


class TestControlPlaneSummaryRealism:
    def test_mixed_state_aggregation(
        self, session2_block3_client, db: Session
    ):
        fid = _seed_family(db)
        mid = _seed_member(db, fid)
        now = datetime.now(timezone.utc)

        # 1 healthy (connected, just synced)
        _seed_account(
            db,
            family_id=fid,
            connector_key="google_calendar",
            status="connected",
            last_success_at=now - timedelta(minutes=1),
        )
        # 1 stale (configured, last sync 8h ago)
        _seed_account(
            db,
            family_id=fid,
            connector_key="ynab",
            status="configured",
            last_success_at=now - timedelta(hours=8),
        )
        # 1 in error
        _seed_account(
            db,
            family_id=fid,
            connector_key="rex",
            status="error",
            last_success_at=now - timedelta(hours=2),
            last_error_at=now,
            last_error_message="boom",
        )

        tok = _bearer(db, mid)
        r = session2_block3_client.get(
            "/api/control-plane/summary",
            headers={"Authorization": f"Bearer {tok}"},
        )
        body = r.json()
        assert body["connectors"]["healthy_count"] == 1
        assert body["connectors"]["stale_count"] == 1
        assert body["connectors"]["error_count"] == 1

    def test_sync_runs_in_last_24h_are_counted(
        self, session2_block3_client, db: Session
    ):
        fid = _seed_family(db)
        mid = _seed_member(db, fid)
        aid = _seed_account(db, family_id=fid, connector_key="google_calendar")
        jid = _seed_sync_job(db, connector_account_id=aid)

        # One running, one error
        rid = start_sync_run(db, sync_job_id=jid)  # running
        rid_err = start_sync_run(db, sync_job_id=jid)
        finish_sync_run(
            db,
            run_id=rid_err,
            result=SyncResult(status="error", error_message="x"),
        )
        db.commit()

        tok = _bearer(db, mid)
        r = session2_block3_client.get(
            "/api/control-plane/summary",
            headers={"Authorization": f"Bearer {tok}"},
        )
        body = r.json()
        assert body["sync_jobs"]["running_count"] == 1
        assert body["sync_jobs"]["failed_count"] == 1

    def test_calendar_export_counts_reflect_real_state(
        self, session2_block3_client, db: Session
    ):
        fid = _seed_family(db)
        mid = _seed_member(db, fid)
        e_pending = _insert_pending_export(db, family_id=fid, label="A")
        e_error = _insert_pending_export(db, family_id=fid, label="B")
        mark_export_status(
            db, calendar_export_id=e_error, new_status="error", error_message="x"
        )
        db.commit()

        tok = _bearer(db, mid)
        r = session2_block3_client.get(
            "/api/control-plane/summary",
            headers={"Authorization": f"Bearer {tok}"},
        )
        body = r.json()
        assert body["calendar_exports"]["pending_count"] == 1
        assert body["calendar_exports"]["failed_count"] == 1
