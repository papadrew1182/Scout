import uuid
from datetime import datetime

from pydantic import BaseModel


class RoleTierRead(BaseModel):
    id: uuid.UUID
    name: str
    permissions: dict
    behavior_config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleTierOverrideRead(BaseModel):
    id: uuid.UUID
    family_member_id: uuid.UUID
    role_tier_id: uuid.UUID
    override_permissions: dict
    override_behavior: dict
    created_at: datetime

    model_config = {"from_attributes": True}
