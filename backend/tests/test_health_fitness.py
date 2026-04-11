"""Tests for health_fitness_service.

Covers:
- create / read / update / delete summaries and activity records
- source validation
- activity_type validation
- ended_at >= started_at validation
- non-negative numeric DB constraints
- one-summary-per-member-per-date uniqueness
- latest summary helper
- recent activity helper + ordering
- list filters (date range, activity type)
- tenant isolation
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember
from app.models.health_fitness import ActivityRecord, HealthSummary
from app.schemas.health_fitness import (
    ActivityRecordCreate,
    ActivityRecordUpdate,
    HealthSummaryCreate,
    HealthSummaryUpdate,
)
from app.services.health_fitness_service import (
    create_activity_record,
    create_health_summary,
    delete_activity_record,
    delete_health_summary,
    get_activity_record,
    get_health_summary,
    get_latest_summary,
    list_activity_records,
    list_health_summaries,
    list_recent_activity,
    update_activity_record,
    update_health_summary,
)


def _dt(y, m, d, h=12, minute=0):
    return pytz.timezone("America/Chicago").localize(datetime(y, m, d, h, minute))


# ---------------------------------------------------------------------------
# Health Summaries
# ---------------------------------------------------------------------------

class TestHealthSummaryCreate:
    def test_create_basic(self, db: Session, family, adults):
        andrew = adults["robert"]
        summary = create_health_summary(
            db, family.id,
            HealthSummaryCreate(
                family_member_id=andrew.id,
                summary_date=date(2026, 4, 9),
                steps=8243,
                active_minutes=42,
                resting_heart_rate=58,
                sleep_minutes=432,
                weight_grams=81600,
                source="apple_health",
            ),
        )
        assert summary.id is not None
        assert summary.steps == 8243
        assert summary.source == "apple_health"

    def test_create_partial(self, db: Session, family, adults):
        # Sally with only steps
        summary = create_health_summary(
            db, family.id,
            HealthSummaryCreate(
                family_member_id=adults["megan"].id,
                summary_date=date(2026, 4, 9),
                steps=7234,
            ),
        )
        assert summary.steps == 7234
        assert summary.weight_grams is None
        assert summary.resting_heart_rate is None

    def test_invalid_source_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            create_health_summary(
                db, family.id,
                HealthSummaryCreate(
                    family_member_id=adults["robert"].id,
                    summary_date=date(2026, 4, 9),
                    source="fitbit",
                ),
            )
        assert exc.value.status_code == 400

    def test_negative_steps_rejected_at_db(self, db: Session, family, adults):
        bad = HealthSummary(
            family_id=family.id,
            family_member_id=adults["robert"].id,
            summary_date=date(2026, 4, 9),
            steps=-100,
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_duplicate_member_date_rejected(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_health_summary(
            db, family.id,
            HealthSummaryCreate(
                family_member_id=andrew.id,
                summary_date=date(2026, 4, 9),
                steps=1000,
            ),
        )
        with pytest.raises(IntegrityError):
            create_health_summary(
                db, family.id,
                HealthSummaryCreate(
                    family_member_id=andrew.id,
                    summary_date=date(2026, 4, 9),
                    steps=2000,
                ),
            )


class TestHealthSummaryRetrieval:
    def test_latest_summary(self, db: Session, family, adults):
        andrew = adults["robert"]
        for d in [4, 6, 9, 7]:  # out of order
            create_health_summary(
                db, family.id,
                HealthSummaryCreate(
                    family_member_id=andrew.id,
                    summary_date=date(2026, 4, d),
                    steps=d * 100,
                ),
            )
        latest = get_latest_summary(db, family.id, andrew.id)
        assert latest is not None
        assert latest.summary_date == date(2026, 4, 9)

    def test_latest_summary_none_when_empty(self, db: Session, family, adults):
        latest = get_latest_summary(db, family.id, adults["robert"].id)
        assert latest is None

    def test_list_filters_by_member(self, db: Session, family, adults):
        andrew = adults["robert"]
        sally = adults["megan"]
        create_health_summary(db, family.id, HealthSummaryCreate(
            family_member_id=andrew.id, summary_date=date(2026, 4, 9), steps=100))
        create_health_summary(db, family.id, HealthSummaryCreate(
            family_member_id=sally.id, summary_date=date(2026, 4, 9), steps=200))

        results = list_health_summaries(db, family.id, family_member_id=andrew.id)
        assert len(results) == 1
        assert results[0].steps == 100

    def test_list_filters_by_date_range(self, db: Session, family, adults):
        andrew = adults["robert"]
        for d in [3, 6, 9, 12]:
            create_health_summary(db, family.id, HealthSummaryCreate(
                family_member_id=andrew.id, summary_date=date(2026, 4, d), steps=100))
        results = list_health_summaries(
            db, family.id,
            start_date=date(2026, 4, 5),
            end_date=date(2026, 4, 10),
        )
        dates = {s.summary_date for s in results}
        assert dates == {date(2026, 4, 6), date(2026, 4, 9)}


class TestHealthSummaryUpdateDelete:
    def test_update(self, db: Session, family, adults):
        summary = create_health_summary(db, family.id, HealthSummaryCreate(
            family_member_id=adults["robert"].id,
            summary_date=date(2026, 4, 9),
            steps=1000,
        ))
        updated = update_health_summary(
            db, family.id, summary.id,
            HealthSummaryUpdate(steps=5000, notes="Updated"),
        )
        assert updated.steps == 5000
        assert updated.notes == "Updated"

    def test_delete(self, db: Session, family, adults):
        summary = create_health_summary(db, family.id, HealthSummaryCreate(
            family_member_id=adults["robert"].id,
            summary_date=date(2026, 4, 9),
            steps=1000,
        ))
        delete_health_summary(db, family.id, summary.id)
        with pytest.raises(HTTPException) as exc:
            get_health_summary(db, family.id, summary.id)
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Activity Records
# ---------------------------------------------------------------------------

class TestActivityCreate:
    def test_create_run(self, db: Session, family, adults):
        record = create_activity_record(
            db, family.id,
            ActivityRecordCreate(
                family_member_id=adults["robert"].id,
                activity_type="run",
                title="Morning easy run",
                started_at=_dt(2026, 4, 9, 6, 30),
                ended_at=_dt(2026, 4, 9, 7, 8),
                duration_seconds=2280,
                distance_meters=5200,
                calories=412,
                source="nike_run_club",
            ),
        )
        assert record.id is not None
        assert record.activity_type == "run"
        assert record.distance_meters == 5200

    def test_invalid_activity_type_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            create_activity_record(
                db, family.id,
                ActivityRecordCreate(
                    family_member_id=adults["robert"].id,
                    activity_type="parkour",
                    started_at=_dt(2026, 4, 9, 6),
                ),
            )
        assert exc.value.status_code == 400

    def test_invalid_source_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            create_activity_record(
                db, family.id,
                ActivityRecordCreate(
                    family_member_id=adults["robert"].id,
                    activity_type="run",
                    started_at=_dt(2026, 4, 9, 6),
                    source="garmin",
                ),
            )
        assert exc.value.status_code == 400

    def test_ended_before_started_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            create_activity_record(
                db, family.id,
                ActivityRecordCreate(
                    family_member_id=adults["robert"].id,
                    activity_type="run",
                    started_at=_dt(2026, 4, 9, 7),
                    ended_at=_dt(2026, 4, 9, 6),
                ),
            )
        assert exc.value.status_code == 400

    def test_negative_distance_rejected_at_db(self, db: Session, family, adults):
        bad = ActivityRecord(
            family_id=family.id,
            family_member_id=adults["robert"].id,
            activity_type="run",
            started_at=_dt(2026, 4, 9, 6),
            distance_meters=-1000,
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()


class TestActivityRetrieval:
    def test_recent_orders_by_started_at_desc(self, db: Session, family, adults):
        andrew = adults["robert"]
        for h in [6, 14, 8, 20]:
            create_activity_record(db, family.id, ActivityRecordCreate(
                family_member_id=andrew.id,
                activity_type="walk",
                title=f"At hour {h}",
                started_at=_dt(2026, 4, 9, h),
            ))
        results = list_recent_activity(db, family.id, andrew.id, limit=10)
        hours = [r.started_at.hour for r in results]
        # Compare ordering ignoring tz conversion (all same tz)
        assert hours == sorted(hours, reverse=True)

    def test_recent_limit_respected(self, db: Session, family, adults):
        andrew = adults["robert"]
        for i in range(8):
            create_activity_record(db, family.id, ActivityRecordCreate(
                family_member_id=andrew.id,
                activity_type="walk",
                started_at=_dt(2026, 4, i + 1, 12),
            ))
        results = list_recent_activity(db, family.id, andrew.id, limit=5)
        assert len(results) == 5

    def test_list_filters_by_activity_type(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_activity_record(db, family.id, ActivityRecordCreate(
            family_member_id=andrew.id, activity_type="run", started_at=_dt(2026, 4, 9, 6)))
        create_activity_record(db, family.id, ActivityRecordCreate(
            family_member_id=andrew.id, activity_type="yoga", started_at=_dt(2026, 4, 9, 7)))

        results = list_activity_records(db, family.id, activity_type="run")
        assert len(results) == 1
        assert results[0].activity_type == "run"

    def test_list_filters_by_time_range(self, db: Session, family, adults):
        andrew = adults["robert"]
        for d in [5, 7, 9, 11]:
            create_activity_record(db, family.id, ActivityRecordCreate(
                family_member_id=andrew.id,
                activity_type="walk",
                started_at=_dt(2026, 4, d, 12),
            ))
        results = list_activity_records(
            db, family.id,
            start=_dt(2026, 4, 6, 0),
            end=_dt(2026, 4, 10, 23),
        )
        days = {r.started_at.day for r in results}
        assert days == {7, 9}


class TestActivityUpdateDelete:
    def test_update(self, db: Session, family, adults):
        record = create_activity_record(db, family.id, ActivityRecordCreate(
            family_member_id=adults["robert"].id,
            activity_type="run",
            started_at=_dt(2026, 4, 9, 6),
        ))
        updated = update_activity_record(
            db, family.id, record.id,
            ActivityRecordUpdate(title="Renamed", calories=300),
        )
        assert updated.title == "Renamed"
        assert updated.calories == 300

    def test_delete(self, db: Session, family, adults):
        record = create_activity_record(db, family.id, ActivityRecordCreate(
            family_member_id=adults["robert"].id,
            activity_type="run",
            started_at=_dt(2026, 4, 9, 6),
        ))
        delete_activity_record(db, family.id, record.id)
        with pytest.raises(HTTPException) as exc:
            get_activity_record(db, family.id, record.id)
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_get_summary_from_wrong_family_404(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="X", role="adult")
        db.add(other_member)
        db.flush()
        summary = create_health_summary(db, other.id, HealthSummaryCreate(
            family_member_id=other_member.id,
            summary_date=date(2026, 4, 9),
            steps=100,
        ))
        with pytest.raises(HTTPException) as exc:
            get_health_summary(db, family.id, summary.id)
        assert exc.value.status_code == 404

    def test_list_activity_only_returns_own_family(self, db: Session, family, adults):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="X", role="adult")
        db.add(other_member)
        db.flush()

        create_activity_record(db, family.id, ActivityRecordCreate(
            family_member_id=adults["robert"].id,
            activity_type="run",
            title="Mine",
            started_at=_dt(2026, 4, 9, 6),
        ))
        create_activity_record(db, other.id, ActivityRecordCreate(
            family_member_id=other_member.id,
            activity_type="run",
            title="Theirs",
            started_at=_dt(2026, 4, 9, 6),
        ))

        results = list_activity_records(db, family.id)
        titles = {r.title for r in results}
        assert "Mine" in titles
        assert "Theirs" not in titles
