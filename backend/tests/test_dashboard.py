"""Tests for dashboard aggregation and action inbox.

Covers:
- personal dashboard returns compact data
- parent dashboard returns child statuses + health
- child dashboard returns encouragement + progress
- action inbox: adults only, children get 403
- family isolation
"""

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember
from app.schemas.grocery import GroceryItemCreate, PurchaseRequestCreate
from app.services import dashboard_service, grocery_service


class TestPersonalDashboard:
    def test_returns_compact_data(self, db: Session, family, adults):
        andrew = adults["robert"]
        result = dashboard_service.personal_dashboard(db, family.id, andrew.id)

        assert result["member_name"] == "Robert"
        assert "date" in result
        assert "top_tasks" in result
        assert "events_today" in result
        assert "meals_today" in result
        assert "unpaid_bills_count" in result
        assert "grocery_items_count" in result


class TestParentDashboard:
    def test_returns_child_statuses(self, db: Session, family, adults, children):
        andrew = adults["robert"]
        result = dashboard_service.parent_dashboard(db, family.id, andrew.id)

        assert "children" in result
        assert len(result["children"]) == 3
        child_names = {c["name"] for c in result["children"]}
        assert "Sadie" in child_names

    def test_returns_household_health(self, db: Session, family, adults, children):
        andrew = adults["robert"]
        result = dashboard_service.parent_dashboard(db, family.id, andrew.id)

        assert "household_health" in result
        assert "status" in result["household_health"]
        assert "reasons" in result["household_health"]

    def test_includes_pending_actions(self, db: Session, family, adults, children):
        sadie = children["sadie"]
        grocery_service.create_grocery_item(
            db, family.id, sadie.id, GroceryItemCreate(title="Chips")
        )

        andrew = adults["robert"]
        result = dashboard_service.parent_dashboard(db, family.id, andrew.id)
        assert result["pending_actions_count"] >= 1

    def test_child_cannot_access(self, db: Session, family, children):
        with pytest.raises(HTTPException) as exc:
            dashboard_service.parent_dashboard(db, family.id, children["sadie"].id)
        assert exc.value.status_code == 403


class TestChildDashboard:
    def test_returns_encouragement(self, db: Session, family, children):
        sadie = children["sadie"]
        result = dashboard_service.child_dashboard(db, family.id, sadie.id)

        assert result["member_name"] == "Sadie"
        assert "encouragement" in result
        assert "weekly_wins" in result
        assert "balance_cents" in result

    def test_returns_events_and_meals(self, db: Session, family, children):
        sadie = children["sadie"]
        result = dashboard_service.child_dashboard(db, family.id, sadie.id)

        assert "events_today" in result
        assert "meals_today" in result


class TestActionInbox:
    def test_adult_can_list(self, db: Session, family, adults, children):
        sadie = children["sadie"]
        grocery_service.create_purchase_request(
            db, family.id, sadie.id, PurchaseRequestCreate(title="Book")
        )

        andrew = adults["robert"]
        items = dashboard_service.list_action_items(db, family.id, andrew.id)
        assert any(a["title"] and "Book" in a["title"] for a in items)

    def test_child_cannot_list(self, db: Session, family, children):
        with pytest.raises(HTTPException) as exc:
            dashboard_service.list_action_items(db, family.id, children["sadie"].id)
        assert exc.value.status_code == 403

    def test_resolved_items_filterable(self, db: Session, family, adults, children):
        req = grocery_service.create_purchase_request(
            db, family.id, children["sadie"].id, PurchaseRequestCreate(title="Toy")
        )
        from app.schemas.grocery import ReviewAction
        grocery_service.approve_purchase_request(db, family.id, adults["robert"].id, req.id, ReviewAction())

        pending = dashboard_service.list_action_items(db, family.id, adults["robert"].id, "pending")
        resolved = dashboard_service.list_action_items(db, family.id, adults["robert"].id, "resolved")

        assert not any(a["title"] and "Toy" in a["title"] for a in pending)
        assert any(a["title"] and "Toy" in a["title"] for a in resolved)


class TestFamilyIsolation:
    def test_personal_dashboard_scoped(self, db: Session, family, adults):
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="X", role="adult")
        db.add(other_member)
        db.flush()

        result = dashboard_service.personal_dashboard(db, family.id, adults["robert"].id)
        assert result["member_name"] == "Robert"

        with pytest.raises(Exception):
            dashboard_service.personal_dashboard(db, family.id, other_member.id)
