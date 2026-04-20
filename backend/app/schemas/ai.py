import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ConfirmToolPayload(BaseModel):
    """Inline confirmation of a previously-gated tool.

    Sent back to /api/ai/chat when the user taps 'Confirm' on a
    pending_confirmation card in the ScoutPanel. Bypasses the LLM round
    and re-executes the tool with confirmed=true inside the same
    conversation.
    """

    tool_name: str = Field(min_length=1, max_length=120)
    arguments: dict


class ChatRequest(BaseModel):
    family_id: uuid.UUID | None = None  # Optional: route derives from actor session
    member_id: uuid.UUID | None = None  # Optional: route derives from actor session
    surface: str = Field(default="personal", pattern="^(personal|parent|child)$")
    message: str = Field(default="", max_length=4000)
    conversation_id: uuid.UUID | None = None
    confirm_tool: ConfirmToolPayload | None = None
    # Tier 4 F15: distinct planner mode. Defaults to ordinary 'chat'
    # so the long tool loop and extra planner prompt block only apply
    # when the client explicitly opts in (parent dashboard button,
    # planner deep-link, etc).
    intent: str = Field(
        default="chat",
        pattern="^(chat|weekly_plan)$",
    )

    # Optional storage path for an image/PDF attachment uploaded via
    # POST /api/storage/upload. When set, the backend downloads the file
    # from Supabase Storage and includes it as a Claude vision content
    # block in the Anthropic API call.
    attachment_path: str | None = None

    @model_validator(mode="after")
    def _require_message_or_confirm(self) -> "ChatRequest":
        if not self.message.strip() and self.confirm_tool is None:
            raise ValueError("message is required unless confirm_tool is provided")
        return self


class HandoffPayload(BaseModel):
    entity_type: str
    entity_id: str
    route_hint: str
    summary: str


class PendingConfirmation(BaseModel):
    tool_name: str
    arguments: dict
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    tool_calls_made: int
    model: str
    tokens: dict
    handoff: HandoffPayload | None = None
    pending_confirmation: PendingConfirmation | None = None


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
    conversation_kind: str = "chat"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumableConversation(BaseModel):
    """Envelope returned by GET /api/ai/conversations/resumable.

    All fields null when no prior conversation qualifies for
    auto-resume. `preview` is the first user message trimmed to 120
    chars so the UI can show "You were asking about..." without
    fetching the full thread."""

    conversation_id: uuid.UUID | None
    updated_at: datetime | None
    preview: str | None
    kind: str | None


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str | None
    tool_calls: dict | None
    tool_results: dict | None
    model: str | None
    token_usage: dict | None
    # Attachment metadata stored when the user sent an image/PDF.
    # Shape: {"attachment_path": "...", "attachment_url": "..."} | None
    # Maps to the `metadata` column via the model's `attachment_meta` alias.
    attachment_meta: dict | None = None
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
