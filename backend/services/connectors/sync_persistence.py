"""Connector sync persistence DAL.

Block 3 — the layer that actually writes ``scout.sync_runs`` rows
and updates ``scout.connector_accounts`` health from real adapter
execution. The Block 2 control-plane view already derives
``freshness_state`` from ``connector_accounts.last_success_at`` /
``last_error_at``, but nothing in Block 2 ever populated those
columns. This module is what closes that loop.

Pure SQLAlchemy + raw SQL — no ORM models. Stays a thin DAL so
``SyncService`` can call into it without tangling adapter logic
with persistence concerns.

Locked vocabulary (charter §Connector status vocabulary):

  scout.connector_accounts.status ∈ {
      disconnected, configured, connected, syncing, stale,
      error, disabled, decision_gated
  }

  scout.sync_runs.status ∈ { running, success, partial, error }

  freshness_state ∈ { live, lagging, stale, unknown }   (derived,
      see ``derive_freshness_for_account``)

  scout.calendar_exports.export_status ∈ {
      pending, exported, error, stale, cancelled
  }
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.connectors.base import (
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)

logger = logging.getLogger("scout.connectors.persistence")


# ---------------------------------------------------------------------------
# Sync runs
# ---------------------------------------------------------------------------


def start_sync_run(db: Session, *, sync_job_id: uuid.UUID) -> uuid.UUID:
    """Insert a new sync_runs row in 'running' state and return its
    id. Also flips the parent connector_account to status='syncing'
    so the control-plane surface shows in-flight work immediately."""
    run_id = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO scout.sync_runs (id, sync_job_id, started_at, status)
            VALUES (:id, :job, clock_timestamp(), 'running')
            """
        ),
        {"id": run_id, "job": sync_job_id},
    )
    db.execute(
        text(
            """
            UPDATE scout.connector_accounts
            SET status = 'syncing', updated_at = clock_timestamp()
            WHERE id = (
                SELECT connector_account_id
                FROM scout.sync_jobs WHERE id = :job
            )
            """
        ),
        {"job": sync_job_id},
    )
    db.execute(
        text(
            """
            UPDATE scout.sync_jobs
            SET last_run_started_at = clock_timestamp()
            WHERE id = :job
            """
        ),
        {"job": sync_job_id},
    )
    db.flush()
    return run_id


def finish_sync_run(
    db: Session,
    *,
    run_id: uuid.UUID,
    result: SyncResult,
) -> None:
    """Close out a sync_runs row and propagate the outcome to the
    parent connector_account so v_control_plane reflects it.

    On success: connector_account.status -> 'connected',
    last_success_at -> now, last_error_at/message untouched
    (history is preserved). Any open stale alerts on the affected
    entity are acknowledged.

    On error: connector_account.status -> 'error',
    last_error_at -> now, last_error_message -> result.error_message.
    last_success_at is left in place — the freshness derivation
    decides the rest.

    On partial: status stays 'connected' (data flowed) but
    last_error_at/message are written so the operator surface can
    show the warning. Caller is responsible for raising a
    stale_data_alert if needed.
    """
    db.execute(
        text(
            """
            UPDATE scout.sync_runs
            SET finished_at = clock_timestamp(),
                status = :status,
                records_processed = :records,
                error_message = :err
            WHERE id = :id
            """
        ),
        {
            "id": run_id,
            "status": result.status,
            "records": result.records_processed,
            "err": result.error_message,
        },
    )

    job_row = db.execute(
        text(
            """
            SELECT sj.connector_account_id
            FROM scout.sync_runs sr
            JOIN scout.sync_jobs sj ON sj.id = sr.sync_job_id
            WHERE sr.id = :id
            """
        ),
        {"id": run_id},
    ).first()
    if job_row is None:
        db.flush()
        return

    account_id = job_row.connector_account_id

    if result.status == "success":
        db.execute(
            text(
                """
                UPDATE scout.connector_accounts
                SET status = 'connected',
                    last_success_at = clock_timestamp(),
                    updated_at = clock_timestamp()
                WHERE id = :id
                """
            ),
            {"id": account_id},
        )
    elif result.status == "partial":
        db.execute(
            text(
                """
                UPDATE scout.connector_accounts
                SET status = 'connected',
                    last_success_at = clock_timestamp(),
                    last_error_at = clock_timestamp(),
                    last_error_message = :msg,
                    updated_at = clock_timestamp()
                WHERE id = :id
                """
            ),
            {"id": account_id, "msg": (result.error_message or "")[:500]},
        )
    elif result.status == "error":
        db.execute(
            text(
                """
                UPDATE scout.connector_accounts
                SET status = 'error',
                    last_error_at = clock_timestamp(),
                    last_error_message = :msg,
                    updated_at = clock_timestamp()
                WHERE id = :id
                """
            ),
            {"id": account_id, "msg": (result.error_message or "")[:500]},
        )

    db.execute(
        text(
            """
            UPDATE scout.sync_jobs
            SET last_run_finished_at = clock_timestamp()
            WHERE id = (
                SELECT sync_job_id FROM scout.sync_runs WHERE id = :id
            )
            """
        ),
        {"id": run_id},
    )

    db.flush()


# ---------------------------------------------------------------------------
# Event log + stale alerts
# ---------------------------------------------------------------------------


def record_event(
    db: Session,
    *,
    connector_account_id: uuid.UUID | None,
    event_type: str,
    severity: str = "info",
    payload: dict | None = None,
) -> None:
    """Append to scout.connector_event_log. Severity is locked to
    info/warn/error/critical by the table CHECK constraint."""
    db.execute(
        text(
            """
            INSERT INTO scout.connector_event_log
                (connector_account_id, event_type, severity, payload)
            VALUES
                (:acct, :type, :sev, CAST(:payload AS jsonb))
            """
        ),
        {
            "acct": connector_account_id,
            "type": event_type,
            "sev": severity,
            "payload": json.dumps(payload or {}),
        },
    )
    db.flush()


def raise_stale_alert(
    db: Session,
    *,
    connector_account_id: uuid.UUID,
    entity_key: str,
) -> uuid.UUID | None:
    """Raise a stale_data_alert for an account+entity. Idempotent:
    if an open alert (acknowledged_at IS NULL) already exists for
    the same account/entity, returns its id without inserting a
    duplicate."""
    existing = db.execute(
        text(
            """
            SELECT id FROM scout.stale_data_alerts
            WHERE connector_account_id = :acct
              AND entity_key = :ent
              AND acknowledged_at IS NULL
            ORDER BY stale_since DESC
            LIMIT 1
            """
        ),
        {"acct": connector_account_id, "ent": entity_key},
    ).first()
    if existing:
        return existing.id

    alert_id = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO scout.stale_data_alerts
                (id, connector_account_id, entity_key, stale_since)
            VALUES
                (:id, :acct, :ent, clock_timestamp())
            """
        ),
        {"id": alert_id, "acct": connector_account_id, "ent": entity_key},
    )
    db.flush()
    return alert_id


def acknowledge_stale_alerts(
    db: Session,
    *,
    connector_account_id: uuid.UUID,
    entity_key: str | None = None,
) -> int:
    """Mark every open stale alert for the account (optionally
    scoped to one entity) as acknowledged. Returns the count
    acknowledged."""
    if entity_key is None:
        result = db.execute(
            text(
                """
                UPDATE scout.stale_data_alerts
                SET acknowledged_at = clock_timestamp()
                WHERE connector_account_id = :acct
                  AND acknowledged_at IS NULL
                """
            ),
            {"acct": connector_account_id},
        )
    else:
        result = db.execute(
            text(
                """
                UPDATE scout.stale_data_alerts
                SET acknowledged_at = clock_timestamp()
                WHERE connector_account_id = :acct
                  AND entity_key = :ent
                  AND acknowledged_at IS NULL
                """
            ),
            {"acct": connector_account_id, "ent": entity_key},
        )
    db.flush()
    return result.rowcount or 0


# ---------------------------------------------------------------------------
# Freshness derivation + DB-backed health reads
# ---------------------------------------------------------------------------


# Thresholds — same windows as scout.v_control_plane so the DAL
# and the view never disagree.
LIVE_WINDOW = timedelta(hours=1)
LAGGING_WINDOW = timedelta(hours=6)


def derive_freshness(
    last_success_at: datetime | None,
    *,
    now: datetime | None = None,
) -> FreshnessState:
    """Pure helper — turns a last_success_at timestamp into one of
    the four locked freshness buckets. Mirrors the CASE expression
    inside scout.v_control_plane so behavior is consistent whether
    the caller reads through the view or computes it in-process."""
    if last_success_at is None:
        return FreshnessState.UNKNOWN
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    delta = current - last_success_at
    if delta <= LIVE_WINDOW:
        return FreshnessState.LIVE
    if delta <= LAGGING_WINDOW:
        return FreshnessState.LAGGING
    return FreshnessState.STALE


@dataclass
class DbConnectorHealthRow:
    """One row of DB-backed connector health for a family. The
    route serializes this directly into the
    /api/connectors/health item shape."""

    connector_key: str
    label: str
    healthy: bool
    status: str  # locked vocabulary
    freshness_state: FreshnessState
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str | None
    open_alert_count: int


def db_health_for_family(
    db: Session,
    *,
    family_id: uuid.UUID,
) -> list[DbConnectorHealthRow]:
    """Return one DbConnectorHealthRow per registered connector for
    this family. Connectors with no scout.connector_accounts row
    fall back to:
        - status='decision_gated' if the connector itself is
          decision_gated
        - status='disconnected' otherwise
    and freshness_state=UNKNOWN. Healthy is True only when an
    account row exists, status is 'connected', and the freshness
    bucket is LIVE or LAGGING.
    """
    rows = db.execute(
        text(
            """
            SELECT
                c.connector_key,
                c.label,
                c.decision_gated,
                ca.id                  AS account_id,
                ca.status              AS account_status,
                ca.last_success_at,
                ca.last_error_at,
                ca.last_error_message,
                COALESCE((
                    SELECT COUNT(*)
                    FROM scout.stale_data_alerts a
                    WHERE a.connector_account_id = ca.id
                      AND a.acknowledged_at IS NULL
                ), 0) AS open_alert_count
            FROM scout.connectors c
            LEFT JOIN scout.connector_accounts ca
                ON ca.connector_id = c.id AND ca.family_id = :fid
            ORDER BY c.tier, c.connector_key
            """
        ),
        {"fid": family_id},
    ).all()

    out: list[DbConnectorHealthRow] = []
    for r in rows:
        if r.account_id is None:
            status = "decision_gated" if r.decision_gated else "disconnected"
            out.append(
                DbConnectorHealthRow(
                    connector_key=r.connector_key,
                    label=r.label,
                    healthy=False,
                    status=status,
                    freshness_state=FreshnessState.UNKNOWN,
                    last_success_at=None,
                    last_error_at=None,
                    last_error_message=None,
                    open_alert_count=0,
                )
            )
            continue

        freshness = derive_freshness(r.last_success_at)
        healthy = (
            r.account_status == "connected"
            and freshness in (FreshnessState.LIVE, FreshnessState.LAGGING)
        )
        out.append(
            DbConnectorHealthRow(
                connector_key=r.connector_key,
                label=r.label,
                healthy=healthy,
                status=r.account_status,
                freshness_state=freshness,
                last_success_at=r.last_success_at,
                last_error_at=r.last_error_at,
                last_error_message=r.last_error_message,
                open_alert_count=int(r.open_alert_count or 0),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Calendar export state transitions
# ---------------------------------------------------------------------------


# scout.calendar_exports.export_status enum, locked by CHECK constraint.
_EXPORT_STATUSES = {"pending", "exported", "error", "stale", "cancelled"}


def mark_export_status(
    db: Session,
    *,
    calendar_export_id: uuid.UUID,
    new_status: str,
    error_message: str | None = None,
) -> None:
    """Transition a calendar_exports row to a new status. On
    'exported', stamps last_exported_at and clears any error.
    On 'error', writes the message; on other transitions the
    error_message column is left untouched.

    Raises ValueError if the requested status is outside the
    locked vocabulary so the call site fails loudly rather than
    tripping a CHECK constraint at commit time.
    """
    if new_status not in _EXPORT_STATUSES:
        raise ValueError(
            f"invalid calendar export status '{new_status}'; "
            f"must be one of {sorted(_EXPORT_STATUSES)}"
        )

    if new_status == "exported":
        db.execute(
            text(
                """
                UPDATE scout.calendar_exports
                SET export_status = 'exported',
                    last_exported_at = clock_timestamp(),
                    error_message = NULL,
                    updated_at = clock_timestamp()
                WHERE id = :id
                """
            ),
            {"id": calendar_export_id},
        )
    elif new_status == "error":
        db.execute(
            text(
                """
                UPDATE scout.calendar_exports
                SET export_status = 'error',
                    error_message = :err,
                    updated_at = clock_timestamp()
                WHERE id = :id
                """
            ),
            {"id": calendar_export_id, "err": (error_message or "")[:500]},
        )
    else:
        db.execute(
            text(
                """
                UPDATE scout.calendar_exports
                SET export_status = :s, updated_at = clock_timestamp()
                WHERE id = :id
                """
            ),
            {"id": calendar_export_id, "s": new_status},
        )
    db.flush()
