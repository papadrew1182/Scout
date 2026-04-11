import uuid
from datetime import datetime

from pydantic import BaseModel


class ConnectorConfigRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID | None
    family_member_id: uuid.UUID | None
    connector_name: str
    config: dict
    scope: str
    sync_direction: str
    authority_level: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectorMappingRead(BaseModel):
    id: uuid.UUID
    connector_name: str
    internal_table: str
    internal_id: uuid.UUID
    external_id: str
    metadata_: dict
    created_at: datetime

    model_config = {"from_attributes": True}
