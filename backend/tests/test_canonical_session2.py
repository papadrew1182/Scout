"""Session 2 regression coverage — canonical household + connector platform.

Covers the charter's required test list:

  * migration sanity (scout + connector_* schemas + every table exists)
  * role-tier seed invariants (6 canonical tiers + permissions seeded)
  * connector_mappings uniqueness on (connector_name, external_object_type, external_id)
  * odd/even task assignment rule evaluator
  * 8-week task rotation rule evaluator
  * Daily Win calculation against a fixture
  * endpoint contract shape locked for Session 3
  * stale-data / sync-state basic behaviour
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.connectors import CONNECTOR_REGISTRY, SyncService
from services.connectors.base import FreshnessState


# ---------------------------------------------------------------------------
# Helpers — small, self-contained rule evaluators that the real engine will
# implement. Tests pin the shape so the real implementation lands with a
# target.
# ---------------------------------------------------------------------------


def evaluate_day_parity_rule(
    params: dict[str, str], on_date: date
) -> uuid.UUID:
    """Charter §dog-walk assistant rule. Odd day → one kid, even day →
    the other. Calendar day parity (day-of-month % 2)."""
    parity = on_date.day % 2
    key = "odd" if parity == 1 else "even"
    return uuid.UUID(params[key])


def evaluate_week_rotation_rule(
    params: dict[str, str], on_date: date
) -> dict[str, uuid.UUID]:
    """Charter §Backyard Poop Patrol — owner/assistant swap every
    ``period_weeks`` weeks from an anchor date. Returns the owner +
    assistant for the ISO week containing ``on_date``."""
    anchor = date.fromisoformat(params["anchor_date"])
    period_weeks = int(params.get("period_weeks", 8))
    weeks_since_anchor = (on_date - anchor).days // 7
    period_index = weeks_since_anchor // period_weeks
    if period_index % 2 == 0:
        return {
            "owner": uuid.UUID(params["owner"]),
            "assistant": uuid.UUID(params["assistant"]),
        }
    return {
        "owner": uuid.UUID(params["assistant"]),
        "assistant": uuid.UUID(params["owner"]),
    }


def compute_daily_win(
    required_item_count: int, completed_item_count: int
) -> bool:
    """Charter §Daily Win. All required items complete by deadline
    → Daily Win earned. Any miss → no Win for the day."""
    if required_item_count == 0:
        return False
    return completed_item_count >= required_item_count


# ---------------------------------------------------------------------------
# Migration sanity
# ---------------------------------------------------------------------------


class TestMigrationSanity:
    def test_scout_schema_exists(self, db: Session):
        row = db.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = 'scout'"
            )
        ).first()
        assert row is not None

    def test_connector_schemas_exist(self, db: Session):
        expected = {
            "connector_google_calendar",
            "connector_greenlight",
            "connector_rex",
            "connector_ynab",
            "connector_apple_health",
            "connector_nike_run_club",
        }
        rows = db.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'connector_%'"
            )
        ).all()
        got = {r.schema_name for r in rows}
        missing = expected - got
        assert not missing, f"missing connector schemas: {missing}"

    @pytest.mark.parametrize(
        "table",
        [
            "permissions",
            "role_tier_permissions",
            "user_family_memberships",
            "user_preferences",
            "device_registrations",
            "household_rules",
            "standards_of_done",
            "routine_templates",
            "routine_steps",
            "task_templates",
            "task_assignment_rules",
            "task_occurrences",
            "task_completions",
            "task_exceptions",
            "task_notes",
            "time_blocks",
            "calendar_exports",
            "reward_policies",
            "daily_win_results",
            "allowance_periods",
            "allowance_results",
            "reward_extras_catalog",
            "reward_ledger_entries",
            "settlement_batches",
            "greenlight_exports",
            "connectors",
            "connector_accounts",
            "sync_jobs",
            "sync_runs",
            "sync_cursors",
            "connector_event_log",
            "stale_data_alerts",
            "external_calendar_events",
            "work_context_events",
            "budget_snapshots",
            "bill_snapshots",
            "activity_events",
            "travel_estimates",
        ],
    )
    def test_every_canonical_table_exists(self, db: Session, table: str):
        row = db.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'scout' AND table_name = :t"
            ),
            {"t": table},
        ).first()
        assert row is not None, f"scout.{table} missing from migration 022"

    @pytest.mark.parametrize(
        "view",
        [
            "v_household_today",
            "v_rewards_current_week",
            "v_calendar_publication",
            "v_control_plane",
        ],
    )
    def test_canonical_views_exist(self, db: Session, view: str):
        row = db.execute(
            text(
                "SELECT table_name FROM information_schema.views "
                "WHERE table_schema = 'scout' AND table_name = :v"
            ),
            {"v": view},
        ).first()
        assert row is not None, f"scout.{view} missing"

    @pytest.mark.parametrize(
        "alias",
        [
            "families",
            "family_members",
            "user_accounts",
            "sessions",
            "role_tiers",
            "role_tier_overrides",
            "connector_mappings",
            "connector_configs",
        ],
    )
    def test_foundation_aliased_into_scout(self, db: Session, alias: str):
        row = db.execute(
            text(
                "SELECT table_name FROM information_schema.views "
                "WHERE table_schema = 'scout' AND table_name = :v"
            ),
            {"v": alias},
        ).first()
        assert row is not None, f"scout.{alias} view missing"


# ---------------------------------------------------------------------------
# Role-tier seeds
# ---------------------------------------------------------------------------


class TestRoleTierSeeds:
    def test_all_six_canonical_tiers_present(self, db: Session):
        rows = db.execute(
            text("SELECT name FROM public.role_tiers ORDER BY name")
        ).all()
        names = {r.name for r in rows}
        expected = {
            "PRIMARY_PARENT",
            "PARENT",
            "TEEN",
            "CHILD",
            "YOUNG_CHILD",
            "DISPLAY_ONLY",
        }
        missing = expected - names
        assert not missing, f"missing canonical role tiers: {missing}"

    def test_parent_tiers_have_full_permission_set(self, db: Session):
        rows = db.execute(
            text(
                """
                SELECT p.permission_key
                FROM public.role_tiers rt
                JOIN scout.role_tier_permissions rtp ON rtp.role_tier_id = rt.id
                JOIN scout.permissions p ON p.id = rtp.permission_id
                WHERE rt.name = 'PRIMARY_PARENT'
                """
            )
        ).all()
        keys = {r.permission_key for r in rows}
        # At minimum a primary parent can manage rules + approve payouts +
        # manage connectors.
        assert "household.edit_rules" in keys
        assert "rewards.approve_payout" in keys
        assert "connectors.manage" in keys

    def test_child_tiers_cannot_approve_payouts(self, db: Session):
        rows = db.execute(
            text(
                """
                SELECT p.permission_key
                FROM public.role_tiers rt
                JOIN scout.role_tier_permissions rtp ON rtp.role_tier_id = rt.id
                JOIN scout.permissions p ON p.id = rtp.permission_id
                WHERE rt.name IN ('TEEN', 'CHILD', 'YOUNG_CHILD')
                """
            )
        ).all()
        keys = {r.permission_key for r in rows}
        assert "rewards.approve_payout" not in keys
        assert "household.edit_rules" not in keys


# ---------------------------------------------------------------------------
# connector_mappings uniqueness
# ---------------------------------------------------------------------------


class TestConnectorMappingsUniqueness:
    def test_duplicate_same_object_raises(self, db: Session, family, adults):
        # First insert
        db.execute(
            text(
                """
                INSERT INTO public.connector_mappings
                    (connector_name, internal_table, internal_id, external_id,
                     external_object_type, family_id)
                VALUES
                    ('google_calendar', 'events', :iid, 'evt-1',
                     'calendar_event', :fid)
                """
            ),
            {"iid": uuid.uuid4(), "fid": family.id},
        )
        db.flush()
        # Duplicate on the composite key
        with pytest.raises(Exception):
            db.execute(
                text(
                    """
                    INSERT INTO public.connector_mappings
                        (connector_name, internal_table, internal_id, external_id,
                         external_object_type, family_id)
                    VALUES
                        ('google_calendar', 'events', :iid, 'evt-1',
                         'calendar_event', :fid)
                    """
                ),
                {"iid": uuid.uuid4(), "fid": family.id},
            )
            db.flush()

    def test_same_external_id_different_object_type_allowed(
        self, db: Session, family
    ):
        db.execute(
            text(
                """
                INSERT INTO public.connector_mappings
                    (connector_name, internal_table, internal_id, external_id,
                     external_object_type, family_id)
                VALUES
                    ('google_calendar', 'events', :id1, 'shared-ext-id',
                     'calendar_event', :fid),
                    ('google_calendar', 'task_occurrences', :id2, 'shared-ext-id',
                     'task_occurrence', :fid)
                """
            ),
            {
                "id1": uuid.uuid4(),
                "id2": uuid.uuid4(),
                "fid": family.id,
            },
        )
        # Would raise on flush if the new composite unique was wrong.
        db.flush()


# ---------------------------------------------------------------------------
# Assignment-rule evaluators
# ---------------------------------------------------------------------------


class TestAssignmentRuleEvaluators:
    def test_day_parity_alternates(self):
        sadie = uuid.uuid4()
        townes = uuid.uuid4()
        params = {"odd": str(townes), "even": str(sadie)}
        # Apr 13 = day 13 (odd) → Townes
        assert evaluate_day_parity_rule(params, date(2026, 4, 13)) == townes
        # Apr 14 = day 14 (even) → Sadie
        assert evaluate_day_parity_rule(params, date(2026, 4, 14)) == sadie

    def test_week_rotation_swaps_every_8_weeks(self):
        owner = uuid.uuid4()
        assistant = uuid.uuid4()
        params = {
            "owner": str(owner),
            "assistant": str(assistant),
            "period_weeks": 8,
            "anchor_date": "2026-01-05",  # a Monday
        }
        # Week 0 (Jan 5) → owner=owner
        result = evaluate_week_rotation_rule(params, date(2026, 1, 5))
        assert result["owner"] == owner
        assert result["assistant"] == assistant
        # Week 4 (still inside period 0) → unchanged
        result = evaluate_week_rotation_rule(params, date(2026, 2, 2))
        assert result["owner"] == owner
        # Week 8 (period 1) → swap
        result = evaluate_week_rotation_rule(params, date(2026, 3, 2))
        assert result["owner"] == assistant
        assert result["assistant"] == owner
        # Week 16 (period 2) → swap back
        result = evaluate_week_rotation_rule(params, date(2026, 4, 27))
        assert result["owner"] == owner


# ---------------------------------------------------------------------------
# Daily Win calculation
# ---------------------------------------------------------------------------


class TestDailyWinCalc:
    def test_all_complete_is_a_win(self):
        assert compute_daily_win(4, 4) is True

    def test_any_miss_is_not_a_win(self):
        assert compute_daily_win(4, 3) is False

    def test_zero_required_is_not_a_win(self):
        assert compute_daily_win(0, 0) is False


# ---------------------------------------------------------------------------
# Endpoint contracts
# ---------------------------------------------------------------------------


@pytest.fixture
def session2_client(db):
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


def _bearer(db: Session, member_id):
    from app.models.foundation import Session as SessionModel, UserAccount
    from app.services.auth_service import hash_password

    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"s2-{uuid.uuid4().hex[:8]}@scout.local",
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


class TestCanonicalEndpointContracts:
    def test_me_shape(self, session2_client, db, family, adults):
        tok = _bearer(db, adults["robert"].id)
        r = session2_client.get(
            "/api/me", headers={"Authorization": f"Bearer {tok}"}
        )
        assert r.status_code == 200
        body = r.json()
        assert "user" in body and "family" in body
        assert set(body["user"].keys()) >= {
            "id",
            "email",
            "full_name",
            "role_tier_key",
            "family_member_id",
            "feature_flags",
        }
        assert set(body["family"].keys()) >= {"id", "name", "timezone"}

    def test_family_context_current_shape(
        self, session2_client, db, family, adults, children
    ):
        tok = _bearer(db, adults["robert"].id)
        r = session2_client.get(
            "/api/family/context/current",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) >= {
            "family",
            "date",
            "active_time_block",
            "kids",
            "household_rules",
        }
        assert isinstance(body["kids"], list)
        for k in body["kids"]:
            assert set(k.keys()) >= {
                "family_member_id",
                "name",
                "age",
                "role_tier_key",
            }

    def test_household_today_envelope(self, session2_client, db, family, adults):
        tok = _bearer(db, adults["robert"].id)
        r = session2_client.get(
            "/api/household/today",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) >= {
            "date",
            "summary",
            "blocks",
            "standalone_chores",
            "weekly_items",
        }
        assert set(body["summary"].keys()) >= {
            "due_count",
            "completed_count",
            "late_count",
        }

    def test_rewards_week_current_envelope(
        self, session2_client, db, family, adults
    ):
        tok = _bearer(db, adults["robert"].id)
        r = session2_client.get(
            "/api/rewards/week/current",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "members" in body
        assert "approval" in body
        assert set(body["approval"].keys()) >= {"state"}

    def test_connectors_list_includes_all_nine(
        self, session2_client, db, family, adults
    ):
        tok = _bearer(db, adults["robert"].id)
        r = session2_client.get(
            "/api/connectors",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        keys = {item["connector_key"] for item in body["items"]}
        assert keys == set(CONNECTOR_REGISTRY.keys())
        # Every item has locked shape
        for item in body["items"]:
            assert set(item.keys()) >= {
                "connector_key",
                "label",
                "status",
                "last_sync_at",
            }

    def test_connectors_health_includes_all_nine(
        self, session2_client, db, family, adults
    ):
        tok = _bearer(db, adults["robert"].id)
        r = session2_client.get(
            "/api/connectors/health",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == len(CONNECTOR_REGISTRY)
        for item in body["items"]:
            assert set(item.keys()) >= {
                "connector_key",
                "healthy",
                "freshness_state",
                "last_success_at",
                "last_error_at",
                "last_error_message",
            }
            assert item["freshness_state"] in {
                "live",
                "lagging",
                "stale",
                "unknown",
            }


# ---------------------------------------------------------------------------
# Stale-data / sync-state basics
# ---------------------------------------------------------------------------


class TestConnectorPlatformBasics:
    def test_registry_has_all_nine_connectors(self):
        expected = {
            "google_calendar",
            "hearth_display",
            "greenlight",
            "rex",
            "ynab",
            "apple_health",
            "nike_run_club",
            "google_maps",
            "exxir",
        }
        assert set(CONNECTOR_REGISTRY.keys()) == expected

    def test_sync_service_wraps_notimplemented_as_error_result(self):
        # Block 3 upgraded google_calendar to a quiet operational
        # baseline, so it no longer raises NotImplementedError.
        # We assert the wrapping behavior against an adapter that
        # is still a registry stub (rex is inbound-only and its
        # client wiring is deferred).
        from services.connectors.sync_service import SyncRequest

        svc = SyncService()
        result = svc.run_sync(
            SyncRequest(
                connector_account_id=uuid.uuid4(),
                connector_key="rex",
                entity_key="rex_inbound",
                cursor=None,
                force_backfill=False,
            )
        )
        assert result.status == "error"
        assert "not yet implemented" in (result.error_message or "")

    def test_sync_service_health_check_wraps_notimplemented(self):
        svc = SyncService()
        health = svc.health_check("google_calendar")
        assert health.healthy is False
        assert health.freshness_state == FreshnessState.UNKNOWN

    def test_hearth_display_reports_healthy_no_source_data(self):
        svc = SyncService()
        health = svc.health_check("hearth_display")
        # Hearth has no source data to sync; the adapter reports healthy
        # with an explanatory message so the control plane doesn't
        # misclassify it.
        assert health.healthy is True

    def test_exxir_is_decision_gated(self):
        svc = SyncService()
        health = svc.health_check("exxir")
        assert health.healthy is False
        assert "decision-gated" in (health.last_error_message or "").lower()

    def test_stale_data_alert_can_be_inserted_and_acknowledged(
        self, db: Session, family
    ):
        # Seed a connector_account for the google_calendar connector
        conn_row = db.execute(
            text(
                "SELECT id FROM scout.connectors WHERE connector_key = 'google_calendar'"
            )
        ).first()
        assert conn_row is not None
        acct_id = uuid.uuid4()
        db.execute(
            text(
                """
                INSERT INTO scout.connector_accounts
                    (id, connector_id, family_id, status)
                VALUES
                    (:id, :cid, :fid, 'configured')
                """
            ),
            {"id": acct_id, "cid": conn_row.id, "fid": family.id},
        )
        db.execute(
            text(
                """
                INSERT INTO scout.stale_data_alerts
                    (connector_account_id, entity_key)
                VALUES
                    (:aid, 'calendar_event')
                """
            ),
            {"aid": acct_id},
        )
        db.flush()

        count = db.execute(
            text(
                """
                SELECT COUNT(*)::int AS n
                FROM scout.stale_data_alerts
                WHERE connector_account_id = :aid AND acknowledged_at IS NULL
                """
            ),
            {"aid": acct_id},
        ).scalar()
        assert count == 1

        db.execute(
            text(
                """
                UPDATE scout.stale_data_alerts
                SET acknowledged_at = clock_timestamp()
                WHERE connector_account_id = :aid
                """
            ),
            {"aid": acct_id},
        )
        db.flush()
        unack = db.execute(
            text(
                """
                SELECT COUNT(*)::int AS n
                FROM scout.stale_data_alerts
                WHERE connector_account_id = :aid AND acknowledged_at IS NULL
                """
            ),
            {"aid": acct_id},
        ).scalar()
        assert unack == 0
