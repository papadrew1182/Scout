import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    family_id: uuid.UUID | None = None  # Optional: route derives from actor session
    member_id: uuid.UUID | None = None  # Optional: route derives from actor session
    surface: str = Field(default="personal", pattern="^(personal|parent|child)$")
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    tool_calls_made: int
    model: str
    tokens: dict


class BriefRequest(BaseModel):
    family_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None


class BriefResponse(BaseModel):
    brief: str
    date: str
    model: str


class WeeklyPlanRequest(BaseModel):
    family_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None


class WeeklyPlanResponse(BaseModel):
    plan: str
    week_start: str
    model: str


class StapleMealsRequest(BaseModel):
    family_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None


class StapleMealsResponse(BaseModel):
    suggestions: str
    model: str


class ConversationRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    surface: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str | None
    tool_calls: dict | None
    tool_results: dict | None
    model: str | None
    token_usage: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolAuditRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    actor_member_id: uuid.UUID
    tool_name: str
    arguments: dict
    result_summary: str | None
    target_entity: str | None
    target_id: uuid.UUID | None
    status: str
    error_message: str | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
