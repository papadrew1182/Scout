"""Tests for grocery_service + purchase requests.

Covers:
- create grocery item (adult vs child approval_status)
- list / update / mark purchased
- purchase request create / approve / reject / convert
- child permission restrictions
- family isolation
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

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

    def test_pending_review_list(self, db: Session, family, children):
        sadie = children["sadie"]
        create_grocery_item(db, family.id, sadie.id, GroceryItemCreate(title="Gum"))
        pending = list_pending_review_items(db, family.id)
        assert any(i.title == "Gum" for i in pending)


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
