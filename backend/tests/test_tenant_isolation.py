"""Tests for tenant isolation.

Covers:
- family-scoped queries never leak across families
- member operations require correct family context
"""

import uuid
from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember
from app.models.life_management import Routine
from app.services.family_service import get_member, list_members
from app.services.routine_service import get_routine, list_routines
from app.services.tenant_guard import require_family, require_member_in_family


@pytest.fixture()
def family_b(db: Session) -> Family:
    f = Family(name="Other Family", timezone="America/New_York")
    db.add(f)
    db.flush()
    return f


@pytest.fixture()
def member_b(db: Session, family_b: Family) -> FamilyMember:
    m = FamilyMember(family_id=family_b.id, first_name="Stranger", role="child")
    db.add(m)
    db.flush()
    return m


class TestTenantGuard:
    def test_require_family_nonexistent(self, db: Session):
        with pytest.raises(HTTPException) as exc_info:
            require_family(db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    def test_require_member_wrong_family(self, db: Session, family, member_b):
        with pytest.raises(HTTPException) as exc_info:
            require_member_in_family(db, family.id, member_b.id)
        assert exc_info.value.status_code == 404


class TestFamilyServiceIsolation:
    def test_list_members_only_returns_own_family(self, db: Session, family, children, family_b, member_b):
        members = list_members(db, family.id)
        member_ids = {m.id for m in members}

        assert member_b.id not in member_ids
        assert children["sadie"].id in member_ids

    def test_get_member_from_wrong_family_404(self, db: Session, family, member_b):
        with pytest.raises(HTTPException) as exc_info:
            get_member(db, family.id, member_b.id)
        assert exc_info.value.status_code == 404


class TestRoutineServiceIsolation:
    def test_list_routines_only_returns_own_family(self, db: Session, family, children, sadie_routines, family_b, member_b):
        other_routine = Routine(
            family_id=family_b.id, family_member_id=member_b.id,
            name="Other Routine", block="morning", recurrence="daily",
            due_time_weekday=time(7, 0),
        )
        db.add(other_routine)
        db.flush()

        routines = list_routines(db, family.id)
        routine_ids = {r.id for r in routines}

        assert other_routine.id not in routine_ids
        assert sadie_routines[0].id in routine_ids

    def test_get_routine_from_wrong_family_404(self, db: Session, family, family_b, member_b):
        other_routine = Routine(
            family_id=family_b.id, family_member_id=member_b.id,
            name="Other Routine", block="morning", recurrence="daily",
            due_time_weekday=time(7, 0),
        )
        db.add(other_routine)
        db.flush()

        with pytest.raises(HTTPException) as exc_info:
            get_routine(db, family.id, other_routine.id)
        assert exc_info.value.status_code == 404
