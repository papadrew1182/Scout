"""Grocery items + purchase requests service.

All sources converge into grocery_items: meal_ai, manual, purchase_request.
Children's manual additions default to pending_review.
Purchase requests go through an approval flow before becoming grocery items.

Permission rules:
- list_purchase_requests: children see only their own; adults see all family
- list_pending_review_items: adults only; children get 403
- approve/reject/convert: adults only
"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.grocery import GroceryItem, PurchaseRequest
from app.models.foundation import FamilyMember
from app.schemas.grocery import (
    GroceryItemCreate,
    GroceryItemUpdate,
    PurchaseRequestCreate,
    ReviewAction,
)
from app.services.tenant_guard import require_family, require_member_in_family


def _create_parent_action(
    db: Session,
    family_id: uuid.UUID,
    created_by: uuid.UUID,
    action_type: str,
    title: str,
    detail: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> ParentActionItem:
    item = ParentActionItem(
        family_id=family_id,
        created_by_member_id=created_by,
        action_type=action_type,
        title=title,
        detail=detail,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(item)
    db.flush()
    return item


def _resolve_parent_action(
    db: Session,
    family_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    resolver_id: uuid.UUID,
) -> None:
    stmt = (
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.entity_type == entity_type)
        .where(ParentActionItem.entity_id == entity_id)
        .where(ParentActionItem.status == "pending")
    )
    for action in db.scalars(stmt).all():
        action.status = "resolved"
        action.resolved_by = resolver_id
        action.resolved_at = datetime.now().astimezone()
    db.flush()


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


def create_grocery_item_nocommit(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: GroceryItemCreate,
) -> GroceryItem:
    """Validate + insert a grocery item WITHOUT committing. See
    ``personal_tasks_service.create_personal_task_nocommit`` for
    context — used by the planner bundle apply path."""
    member = require_member_in_family(db, family_id, member_id)

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
    db.flush()

    if member.role == "child":
        _create_parent_action(
            db, family_id, member_id,
            action_type="grocery_review",
            title=f"{member.first_name} added '{payload.title}' to the grocery list",
            entity_type="grocery_item",
            entity_id=item.id,
        )
    return item


def create_grocery_item(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: GroceryItemCreate,
) -> GroceryItem:
    item = create_grocery_item_nocommit(db, family_id, member_id, payload)
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


def list_pending_review_items(
    db: Session,
    family_id: uuid.UUID,
    actor_member_id: uuid.UUID | None = None,
) -> list[GroceryItem]:
    """Items needing parent review. Adults only — children get 403."""
    require_family(db, family_id)
    if actor_member_id:
        actor = require_member_in_family(db, family_id, actor_member_id)
        if actor.role == "child":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children cannot view pending review items")

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
    _require_adult(db, family_id, reviewer_id, "grocery.approve")
    item = get_grocery_item(db, family_id, item_id)
    item.approval_status = "active"
    _resolve_parent_action(db, family_id, "grocery_item", item_id, reviewer_id)
    db.commit()
    db.refresh(item)
    return item


def reject_grocery_item(
    db: Session, family_id: uuid.UUID, reviewer_id: uuid.UUID, item_id: uuid.UUID
) -> GroceryItem:
    _require_adult(db, family_id, reviewer_id, "grocery.approve")
    item = get_grocery_item(db, family_id, item_id)
    item.approval_status = "rejected"
    _resolve_parent_action(db, family_id, "grocery_item", item_id, reviewer_id)
    db.commit()
    db.refresh(item)
    return item


# ============================================================================
# Purchase Requests
# ============================================================================

def list_purchase_requests(
    db: Session,
    family_id: uuid.UUID,
    actor_member_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    status_filter: str | None = None,
    requested_by: uuid.UUID | None = None,
) -> list[PurchaseRequest]:
    require_family(db, family_id)
    stmt = select(PurchaseRequest).where(PurchaseRequest.family_id == family_id)

    if actor_role == "child" and actor_member_id:
        stmt = stmt.where(PurchaseRequest.requested_by_member_id == actor_member_id)

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
    member = require_member_in_family(db, family_id, member_id)

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
    db.flush()

    _create_parent_action(
        db, family_id, member_id,
        action_type="purchase_request",
        title=f"{member.first_name} requested '{payload.title}'",
        detail=payload.details,
        entity_type="purchase_request",
        entity_id=req.id,
    )

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
    _require_adult(db, family_id, reviewer_id, "purchase_request.approve")
    req = get_purchase_request(db, family_id, request_id)
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot approve request with status '{req.status}'")

    req.status = "approved"
    req.reviewed_by_member_id = reviewer_id
    req.reviewed_at = datetime.now().astimezone()
    req.review_note = action.review_note
    _resolve_parent_action(db, family_id, "purchase_request", request_id, reviewer_id)
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
    _require_adult(db, family_id, reviewer_id, "purchase_request.approve")
    req = get_purchase_request(db, family_id, request_id)
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot reject request with status '{req.status}'")

    req.status = "rejected"
    req.reviewed_by_member_id = reviewer_id
    req.reviewed_at = datetime.now().astimezone()
    req.review_note = action.review_note
    _resolve_parent_action(db, family_id, "purchase_request", request_id, reviewer_id)
    db.commit()
    db.refresh(req)
    return req


def convert_purchase_request_to_grocery(
    db: Session,
    family_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    request_id: uuid.UUID,
) -> tuple[PurchaseRequest, GroceryItem]:
    _require_adult(db, family_id, reviewer_id, "purchase_request.approve")
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
    _resolve_parent_action(db, family_id, "purchase_request", request_id, reviewer_id)
    db.commit()
    db.refresh(req)
    db.refresh(item)
    return req, item


# ============================================================================
# Parent Action Items
# ============================================================================

def list_parent_action_items(
    db: Session, family_id: uuid.UUID, status_filter: str = "pending"
) -> list[ParentActionItem]:
    require_family(db, family_id)
    stmt = (
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.status == status_filter)
        .order_by(ParentActionItem.created_at.desc())
    )
    return list(db.scalars(stmt).all())


# ============================================================================
# Helpers
# ============================================================================

def _require_adult(db: Session, family_id: uuid.UUID, member_id: uuid.UUID, permission_key: str = "grocery.approve") -> FamilyMember:
    """Preserved for Phase 2: now checks the permission tier instead of role==adult."""
    from app.services.permissions import resolve_effective_permissions
    member = require_member_in_family(db, family_id, member_id)
    perms = resolve_effective_permissions(db, member_id)
    if not perms.get(permission_key, False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission required: {permission_key}")
    return member
