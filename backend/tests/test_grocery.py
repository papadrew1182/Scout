"""Tests for grocery_service + purchase requests.

Covers:
- create grocery item (adult vs child approval_status)
- list / update / mark purchased
- purchase request create / approve / reject / convert
- child permission restrictions (own requests only, no pending-review)
- parent action item creation on child submissions
- family isolation
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.foundation import Family, FamilyMember
from app.models.grocery import GroceryItem, PurchaseRequest
from app.schemas.grocery import GroceryItemCreate, GroceryItemUpdate, PurchaseRequestCreate, ReviewAction
from app.services.grocery_service import (
    approve_grocery_item,
    approve_purchase_request,
    convert_purchase_request_to_grocery,
    create_grocery_item,
    create_purchase_request,
    list_grocery_items,
    list_parent_action_items,
    list_pending_review_items,
    list_purchase_requests,
    reject_purchase_request,
    update_grocery_item,
)


class TestGroceryItemCreate:
    def test_adult_creates_active_item(self, db: Session, family, adults):
        andrew = adults["robert"]
        item = create_grocery_item(db, family.id, andrew.id, GroceryItemCreate(title="Milk"))
        assert item.title == "Milk"
        assert item.approval_status == "active"
        assert item.source == "manual"

    def test_child_creates_pending_review_item(self, db: Session, family, children):
        sadie = children["sadie"]
        item = create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Candy"))
        assert item.approval_status == "pending_review"

    def test_meal_ai_source(self, db: Session, family, adults):
        item = create_grocery_item(
            db, family.id, adults["robert"].id,
            GroceryItemCreate(title="Chicken thighs", source="meal_ai"),
        )
        assert item.source == "meal_ai"
        assert item.approval_status == "active"


class TestGroceryItemList:
    def test_list_excludes_purchased(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_grocery_item(db, family.id, andrew.id, GroceryItemCreate(title="A"))
        b = create_grocery_item(db, family.id, andrew.id, GroceryItemCreate(title="B"))
        update_grocery_item(db, family.id, andrew.id, b.id, GroceryItemUpdate(is_purchased=True))

        items = list_grocery_items(db, family.id)
        titles = {i.title for i in items}
        assert "A" in titles
        assert "B" not in titles

    def test_pending_review_list_adult(self, db: Session, family, adults, children):
        sadie = children["sadie"]
        andrew = adults["robert"]
        create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Gum"))
        pending = list_pending_review_items(db, family.id, actor_member_id=andrew.id)
        assert any(i.title == "Gum" for i in pending)


class TestPendingReviewPermissions:
    def test_child_cannot_view_pending_review(self, db: Session, family, children):
        sadie = children["sadie"]
        create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Test"))
        with pytest.raises(HTTPException) as exc:
            list_pending_review_items(db, family.id, actor_member_id=sadie.id)
        assert exc.value.status_code == 403

    def test_adult_can_view_pending_review(self, db: Session, family, adults, children):
        sadie = children["sadie"]
        andrew = adults["robert"]
        create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Pending item"))
        items = list_pending_review_items(db, family.id, actor_member_id=andrew.id)
        assert any(i.title == "Pending item" for i in items)


class TestGroceryItemApproval:
    def test_adult_can_approve(self, db: Session, family, adults, children):
        sadie = children["sadie"]
        item = create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Cookies"))
        approved = approve_grocery_item(db, family.id, adults["robert"].id, item.id)
        assert approved.approval_status == "active"

    def test_child_cannot_change_approval(self, db: Session, family, adults, children):
        andrew = adults["robert"]
        item = create_grocery_item(db, family.id, andrew.id, GroceryItemCreate(title="Bread"))
        with pytest.raises(HTTPException) as exc:
            update_grocery_item(db, family.id, children["sadie"].id, item.id, GroceryItemUpdate(approval_status="rejected"))
        assert exc.value.status_code == 403


class TestGroceryPurchasedToggle:
    """Children CAN toggle is_purchased (they help with shopping).
    This is the explicit product rule."""

    def test_child_can_mark_purchased(self, db: Session, family, adults, children):
        item = create_grocery_item(db, family.id, adults["robert"].id, GroceryItemCreate(title="Bananas"))
        updated = update_grocery_item(db, family.id, children["sadie"].id, item.id, GroceryItemUpdate(is_purchased=True))
        assert updated.is_purchased is True
        assert updated.purchased_by == children["sadie"].id

    def test_child_can_unmark_purchased(self, db: Session, family, adults, children):
        item = create_grocery_item(db, family.id, adults["robert"].id, GroceryItemCreate(title="Bananas"))
        update_grocery_item(db, family.id, children["sadie"].id, item.id, GroceryItemUpdate(is_purchased=True))
        updated = update_grocery_item(db, family.id, children["sadie"].id, item.id, GroceryItemUpdate(is_purchased=False))
        assert updated.is_purchased is False
        assert updated.purchased_by is None

    def test_adult_can_mark_purchased(self, db: Session, family, adults):
        item = create_grocery_item(db, family.id, adults["robert"].id, GroceryItemCreate(title="Milk"))
        updated = update_grocery_item(db, family.id, adults["robert"].id, item.id, GroceryItemUpdate(is_purchased=True))
        assert updated.is_purchased is True


class TestPurchaseRequestPermissions:
    def test_child_sees_only_own_requests(self, db: Session, family, children):
        sadie = children["sadie"]
        townes = children["townes"]
        create_purchase_request(db, family.id, sadie.id, PurchaseRequestCreate(title="Sadie's book"))
        create_purchase_request(db, family.id, townes.id, PurchaseRequestCreate(title="Townes's game"))

        sadie_reqs = list_purchase_requests(
            db, family.id, actor_member_id=sadie.id, actor_role="child"
        )
        titles = {r.title for r in sadie_reqs}
        assert "Sadie's book" in titles
        assert "Townes's game" not in titles

    def test_child_does_not_see_sibling_request(self, db: Session, family, children):
        townes = children["townes"]
        create_purchase_request(db, family.id, children["sadie"].id, PurchaseRequestCreate(title="Sadie only"))

        townes_reqs = list_purchase_requests(
            db, family.id, actor_member_id=townes.id, actor_role="child"
        )
        assert not any(r.title == "Sadie only" for r in townes_reqs)

    def test_parent_sees_all_family_requests(self, db: Session, family, adults, children):
        create_purchase_request(db, family.id, children["sadie"].id, PurchaseRequestCreate(title="Sadie thing"))
        create_purchase_request(db, family.id, children["townes"].id, PurchaseRequestCreate(title="Townes thing"))

        andrew = adults["robert"]
        all_reqs = list_purchase_requests(
            db, family.id, actor_member_id=andrew.id, actor_role="adult"
        )
        titles = {r.title for r in all_reqs}
        assert "Sadie thing" in titles
        assert "Townes thing" in titles


class TestPurchaseRequests:
    def test_create_request(self, db: Session, family, children):
        sadie = children["sadie"]
        req = create_purchase_request(
            db, family.id, sadie.id,
            PurchaseRequestCreate(title="New headphones", type="personal", urgency="normal"),
        )
        assert req.status == "pending"
        assert req.requested_by_member_id == sadie.id

    def test_approve_request(self, db: Session, family, adults, children):
        req = create_purchase_request(
            db, family.id, children["sadie"].id,
            PurchaseRequestCreate(title="Book"),
        )
        approved = approve_purchase_request(db, family.id, adults["robert"].id, req.id, ReviewAction())
        assert approved.status == "approved"

    def test_reject_request(self, db: Session, family, adults, children):
        req = create_purchase_request(
            db, family.id, children["sadie"].id,
            PurchaseRequestCreate(title="Expensive thing"),
        )
        rejected = reject_purchase_request(
            db, family.id, adults["robert"].id, req.id,
            ReviewAction(review_note="Too expensive"),
        )
        assert rejected.status == "rejected"
        assert rejected.review_note == "Too expensive"

    def test_convert_to_grocery(self, db: Session, family, adults, children):
        req = create_purchase_request(
            db, family.id, children["townes"].id,
            PurchaseRequestCreate(title="Gatorade", type="grocery", quantity=6),
        )
        updated_req, item = convert_purchase_request_to_grocery(db, family.id, adults["robert"].id, req.id)
        assert updated_req.status == "converted"
        assert item.title == "Gatorade"
        assert item.source == "purchase_request"
        assert item.approval_status == "active"
        assert item.purchase_request_id == req.id

    def test_child_cannot_approve(self, db: Session, family, children):
        req = create_purchase_request(
            db, family.id, children["sadie"].id,
            PurchaseRequestCreate(title="Something"),
        )
        with pytest.raises(HTTPException) as exc:
            approve_purchase_request(db, family.id, children["townes"].id, req.id, ReviewAction())
        assert exc.value.status_code == 403

    def test_cannot_approve_non_pending(self, db: Session, family, adults, children):
        req = create_purchase_request(
            db, family.id, children["sadie"].id,
            PurchaseRequestCreate(title="Already done"),
        )
        approve_purchase_request(db, family.id, adults["robert"].id, req.id, ReviewAction())
        with pytest.raises(HTTPException) as exc:
            approve_purchase_request(db, family.id, adults["robert"].id, req.id, ReviewAction())
        assert exc.value.status_code == 400


class TestParentActionItems:
    def test_child_grocery_creates_action(self, db: Session, family, children):
        sadie = children["sadie"]
        create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Chips"))

        actions = list_parent_action_items(db, family.id)
        assert any(a.action_type == "grocery_review" and "Chips" in a.title for a in actions)

    def test_adult_grocery_does_not_create_action(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_grocery_item(db, family.id, andrew.id, GroceryItemCreate(title="Bread"))

        actions = list_parent_action_items(db, family.id)
        assert not any("Bread" in a.title for a in actions)

    def test_purchase_request_creates_action(self, db: Session, family, children):
        townes = children["townes"]
        create_purchase_request(
            db, family.id, townes.id,
            PurchaseRequestCreate(title="Basketball"),
        )

        actions = list_parent_action_items(db, family.id)
        assert any(a.action_type == "purchase_request" and "Basketball" in a.title for a in actions)

    def test_approve_resolves_action(self, db: Session, family, adults, children):
        req = create_purchase_request(
            db, family.id, children["sadie"].id,
            PurchaseRequestCreate(title="Resolved item"),
        )
        approve_purchase_request(db, family.id, adults["robert"].id, req.id, ReviewAction())

        actions = list_parent_action_items(db, family.id, status_filter="pending")
        assert not any("Resolved item" in a.title for a in actions)

        resolved = list_parent_action_items(db, family.id, status_filter="resolved")
        assert any("Resolved item" in a.title for a in resolved)


class TestTenantIsolation:
    def test_list_scoped_to_family(self, db: Session, family, adults):
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="X", role="adult")
        db.add(other_member)
        db.flush()

        create_grocery_item(db, family.id, adults["robert"].id, GroceryItemCreate(title="Mine"))
        create_grocery_item(db, other.id, other_member.id, GroceryItemCreate(title="Theirs"))

        items = list_grocery_items(db, family.id)
        titles = {i.title for i in items}
        assert "Mine" in titles
        assert "Theirs" not in titles
