"""Grocery items + purchase requests service.

All sources converge into grocery_items: meal_ai, manual, purchase_request.
Children's manual additions default to pending_review.
Purchase requests go through an approval flow before becoming grocery items.
"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.grocery import GroceryItem, PurchaseRequest
from app.models.foundation import FamilyMember
from app.schemas.grocery import (
    GroceryItemCreate,
    GroceryItemUpdate,
    PurchaseRequestCreate,
    ReviewAction,
)
from app.services.tenant_guard import require_family, require_member_in_family


# ============================================================================
# Grocery Items
# ============================================================================

def list_grocery_items(
    db: Session,
    family_id: uuid.UUID,
    include_purchased: bool = False,
    include_rejected: bool = False,
) -> list[GroceryItem]:
    require_family(db, family_id)
    stmt = select(GroceryItem).where(GroceryItem.family_id == family_id)
    if not include_purchased:
        stmt = stmt.where(GroceryItem.is_purchased.is_(False))
    if not include_rejected:
        stmt = stmt.where(GroceryItem.approval_status != "rejected")
    stmt = stmt.order_by(GroceryItem.preferred_store.is_(None), GroceryItem.preferred_store, GroceryItem.category, GroceryItem.title)
    return list(db.scalars(stmt).all())


def get_grocery_item(db: Session, family_id: uuid.UUID, item_id: uuid.UUID) -> GroceryItem:
    item = db.get(GroceryItem, item_id)
    if not item or item.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grocery item not found")
    return item


def create_grocery_item(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: GroceryItemCreate,
) -> GroceryItem:
    member = require_member_in_family(db, family_id, member_id)

    # Children's items default to pending_review
    approval = "active"
    if member.role == "child":
        approval = "pending_review"

    item = GroceryItem(
        family_id=family_id,
        added_by_member_id=member_id,
        title=payload.title,
        quantity=payload.quantity,
        unit=payload.unit,
        category=payload.category,
        preferred_store=payload.preferred_store,
        notes=payload.notes,
        source=payload.source,
        approval_status=approval,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_grocery_item(
    db: Session,
    family_id: uuid.UUID,
    actor_member_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: GroceryItemUpdate,
) -> GroceryItem:
    actor = require_member_in_family(db, family_id, actor_member_id)
    item = get_grocery_item(db, family_id, item_id)

    data = payload.model_dump(exclude_unset=True)

    # Children can only mark their own items or items assigned to them
    if actor.role == "child":
        if "approval_status" in data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children cannot change approval status")

    if "is_purchased" in data and data["is_purchased"] and not item.is_purchased:
        data["purchased_at"] = datetime.now().astimezone()
        data["purchased_by"] = actor_member_id
    elif "is_purchased" in data and not data["is_purchased"]:
        data["purchased_at"] = None
        data["purchased_by"] = None

    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def list_pending_review_items(db: Session, family_id: uuid.UUID) -> list[GroceryItem]:
    """Items needing parent review (child-added)."""
    require_family(db, family_id)
    stmt = (
        select(GroceryItem)
        .where(GroceryItem.family_id == family_id)
        .where(GroceryItem.approval_status == "pending_review")
        .order_by(GroceryItem.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def approve_grocery_item(
    db: Session, family_id: uuid.UUID, reviewer_id: uuid.UUID, item_id: uuid.UUID
) -> GroceryItem:
    _require_adult(db, family_id, reviewer_id)
    item = get_grocery_item(db, family_id, item_id)
    item.approval_status = "active"
    db.commit()
    db.refresh(item)
    return item


def reject_grocery_item(
    db: Session, family_id: uuid.UUID, reviewer_id: uuid.UUID, item_id: uuid.UUID
) -> GroceryItem:
    _require_adult(db, family_id, reviewer_id)
    item = get_grocery_item(db, family_id, item_id)
    item.approval_status = "rejected"
    db.commit()
    db.refresh(item)
    return item


# ============================================================================
# Purchase Requests
# ============================================================================

def list_purchase_requests(
    db: Session,
    family_id: uuid.UUID,
    status_filter: str | None = None,
    requested_by: uuid.UUID | None = None,
) -> list[PurchaseRequest]:
    require_family(db, family_id)
    stmt = select(PurchaseRequest).where(PurchaseRequest.family_id == family_id)
    if status_filter:
        stmt = stmt.where(PurchaseRequest.status == status_filter)
    if requested_by:
        stmt = stmt.where(PurchaseRequest.requested_by_member_id == requested_by)
    stmt = stmt.order_by(PurchaseRequest.created_at.desc())
    return list(db.scalars(stmt).all())


def get_purchase_request(db: Session, family_id: uuid.UUID, request_id: uuid.UUID) -> PurchaseRequest:
    req = db.get(PurchaseRequest, request_id)
    if not req or req.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    return req


def create_purchase_request(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: PurchaseRequestCreate,
) -> PurchaseRequest:
    require_member_in_family(db, family_id, member_id)

    req = PurchaseRequest(
        family_id=family_id,
        requested_by_member_id=member_id,
        type=payload.type,
        title=payload.title,
        details=payload.details,
        quantity=payload.quantity,
        unit=payload.unit,
        preferred_brand=payload.preferred_brand,
        preferred_store=payload.preferred_store,
        urgency=payload.urgency,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def approve_purchase_request(
    db: Session,
    family_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    request_id: uuid.UUID,
    action: ReviewAction,
) -> PurchaseRequest:
    _require_adult(db, family_id, reviewer_id)
    req = get_purchase_request(db, family_id, request_id)
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot approve request with status '{req.status}'")

    req.status = "approved"
    req.reviewed_by_member_id = reviewer_id
    req.reviewed_at = datetime.now().astimezone()
    req.review_note = action.review_note
    db.commit()
    db.refresh(req)
    return req


def reject_purchase_request(
    db: Session,
    family_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    request_id: uuid.UUID,
    action: ReviewAction,
) -> PurchaseRequest:
    _require_adult(db, family_id, reviewer_id)
    req = get_purchase_request(db, family_id, request_id)
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot reject request with status '{req.status}'")

    req.status = "rejected"
    req.reviewed_by_member_id = reviewer_id
    req.reviewed_at = datetime.now().astimezone()
    req.review_note = action.review_note
    db.commit()
    db.refresh(req)
    return req


def convert_purchase_request_to_grocery(
    db: Session,
    family_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    request_id: uuid.UUID,
) -> tuple[PurchaseRequest, GroceryItem]:
    """Convert a purchase request into an active grocery item."""
    _require_adult(db, family_id, reviewer_id)
    req = get_purchase_request(db, family_id, request_id)
    if req.status not in ("pending", "approved"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot convert request with status '{req.status}'")

    item = GroceryItem(
        family_id=family_id,
        added_by_member_id=req.requested_by_member_id,
        title=req.title,
        quantity=req.quantity,
        unit=req.unit,
        preferred_store=req.preferred_store,
        notes=req.details,
        source="purchase_request",
        approval_status="active",
        purchase_request_id=req.id,
    )
    db.add(item)
    db.flush()

    req.status = "converted"
    req.linked_grocery_item_id = item.id
    req.reviewed_by_member_id = reviewer_id
    req.reviewed_at = datetime.now().astimezone()
    db.commit()
    db.refresh(req)
    db.refresh(item)
    return req, item


# ============================================================================
# Helpers
# ============================================================================

def _require_adult(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> FamilyMember:
    member = require_member_in_family(db, family_id, member_id)
    if member.role != "adult":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only adults can perform this action")
    return member
