import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- Grocery Items ---

class GroceryItemCreate(BaseModel):
    title: str = Field(min_length=1)
    quantity: Decimal | None = None
    unit: str | None = None
    category: str | None = None
    preferred_store: str | None = None
    notes: str | None = None
    source: str = "manual"


class GroceryItemUpdate(BaseModel):
    title: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    category: str | None = None
    preferred_store: str | None = None
    notes: str | None = None
    is_purchased: bool | None = None
    approval_status: str | None = None


class GroceryItemRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    added_by_member_id: uuid.UUID
    title: str
    quantity: Decimal | None
    unit: str | None
    category: str | None
    preferred_store: str | None
    notes: str | None
    source: str
    approval_status: str
    purchase_request_id: uuid.UUID | None
    weekly_plan_id: uuid.UUID | None
    linked_meal_ref: str | None
    is_purchased: bool
    purchased_at: datetime | None
    purchased_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Purchase Requests ---

class PurchaseRequestCreate(BaseModel):
    type: str = "grocery"
    title: str = Field(min_length=1)
    details: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    preferred_brand: str | None = None
    preferred_store: str | None = None
    urgency: str | None = None


class PurchaseRequestRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    requested_by_member_id: uuid.UUID
    type: str
    title: str
    details: str | None
    quantity: Decimal | None
    unit: str | None
    preferred_brand: str | None
    preferred_store: str | None
    urgency: str | None
    status: str
    linked_grocery_item_id: uuid.UUID | None
    reviewed_by_member_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewAction(BaseModel):
    review_note: str | None = None
