"""Grocery items + purchase requests routes."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.grocery import (
    GroceryItemCreate,
    GroceryItemRead,
    GroceryItemUpdate,
    PurchaseRequestCreate,
    PurchaseRequestRead,
    ReviewAction,
)
from app.services import grocery_service

router = APIRouter(tags=["grocery"])


# ---- Grocery Items ----

@router.get(
    "/families/{family_id}/groceries/current",
    response_model=list[GroceryItemRead],
)
def list_current_grocery_items(
    family_id: uuid.UUID,
    include_purchased: bool = Query(False),
    db: Session = Depends(get_db),
):
    return grocery_service.list_grocery_items(db, family_id, include_purchased=include_purchased)


@router.get(
    "/families/{family_id}/groceries/pending-review",
    response_model=list[GroceryItemRead],
)
def list_pending_review(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.list_pending_review_items(db, family_id, actor.member_id)


@router.post(
    "/families/{family_id}/groceries/items",
    response_model=GroceryItemRead,
    status_code=201,
)
def create_grocery_item(
    family_id: uuid.UUID,
    payload: GroceryItemCreate = ...,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.create_grocery_item(db, family_id, actor.member_id, payload)


@router.patch(
    "/families/{family_id}/groceries/items/{item_id}",
    response_model=GroceryItemRead,
)
def update_grocery_item(
    family_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: GroceryItemUpdate = ...,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.update_grocery_item(db, family_id, actor.member_id, item_id, payload)


@router.post(
    "/families/{family_id}/groceries/items/{item_id}/approve",
    response_model=GroceryItemRead,
)
def approve_grocery_item(
    family_id: uuid.UUID,
    item_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.approve_grocery_item(db, family_id, actor.member_id, item_id)


@router.post(
    "/families/{family_id}/groceries/items/{item_id}/reject",
    response_model=GroceryItemRead,
)
def reject_grocery_item(
    family_id: uuid.UUID,
    item_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.reject_grocery_item(db, family_id, actor.member_id, item_id)


# ---- Purchase Requests ----

@router.get(
    "/families/{family_id}/purchase-requests",
    response_model=list[PurchaseRequestRead],
)
def list_purchase_requests(
    family_id: uuid.UUID,
    status: str | None = Query(None),
    requested_by: uuid.UUID | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.list_purchase_requests(
        db, family_id,
        actor_member_id=actor.member_id,
        actor_role=actor.role,
        status_filter=status,
        requested_by=requested_by,
    )


@router.post(
    "/families/{family_id}/purchase-requests",
    response_model=PurchaseRequestRead,
    status_code=201,
)
def create_purchase_request(
    family_id: uuid.UUID,
    payload: PurchaseRequestCreate = ...,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.create_purchase_request(db, family_id, actor.member_id, payload)


@router.post(
    "/families/{family_id}/purchase-requests/{request_id}/approve",
    response_model=PurchaseRequestRead,
)
def approve_purchase_request(
    family_id: uuid.UUID,
    request_id: uuid.UUID,
    body: ReviewAction = ReviewAction(),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.approve_purchase_request(db, family_id, actor.member_id, request_id, body)


@router.post(
    "/families/{family_id}/purchase-requests/{request_id}/reject",
    response_model=PurchaseRequestRead,
)
def reject_purchase_request(
    family_id: uuid.UUID,
    request_id: uuid.UUID,
    body: ReviewAction = ReviewAction(),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return grocery_service.reject_purchase_request(db, family_id, actor.member_id, request_id, body)


@router.post(
    "/families/{family_id}/purchase-requests/{request_id}/convert-to-grocery",
    response_model=GroceryItemRead,
)
def convert_to_grocery(
    family_id: uuid.UUID,
    request_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    _req, item = grocery_service.convert_purchase_request_to_grocery(
        db, family_id, actor.member_id, request_id
    )
    return item
