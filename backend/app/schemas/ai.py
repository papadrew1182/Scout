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
    # Sprint 04 Phase 1 (migration 046)
    title: str | None = None
    last_active_at: datetime | None = None
    is_pinned: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationStats(BaseModel):
    total_count: int
    active_count: int
    archived_count: int


class ConversationCreateRequest(BaseModel):
    first_message: str | None = Field(default=None, max_length=4000)


class ConversationPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    is_pinned: bool | None = None


class ArchiveOlderRequest(BaseModel):
    days: int = Field(ge=1, le=365)


class PersonalityConfig(BaseModel):
    """Merged personality view returned by GET routes. All keys populated
    from tier defaults even when the member has no member_config row."""

    tone: str
    vocabulary_level: str
    formality: str
    humor: str
    proactivity: str
    verbosity: str
    notes_to_self: str = ""
    role_hints: str = ""


class PersonalityPatchRequest(BaseModel):
    """PATCH body. All fields optional; omitted ones are left alone.
    Unknown keys rejected server-side (see ai_personality_service.validate_payload)."""

    tone: str | None = None
    vocabulary_level: str | None = None
    formality: str | None = None
    humor: str | None = None
    proactivity: str | None = None
    verbosity: str | None = None
    notes_to_self: str | None = None
    role_hints: str | None = None

    model_config = {"extra": "forbid"}


class PersonalityResponse(BaseModel):
    """GET response shape. Includes stored (raw member_config value or
    None), resolved (stored overlaid on tier defaults), and a
    backend-composed preamble preview the UI can render verbatim."""

    stored: dict | None
    resolved: PersonalityConfig
    preamble: str


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


class MessagePage(BaseModel):
    """Paginated response for GET /api/ai/conversations/{id}/messages.

    Returns the newest ``limit`` messages before ``before_message_id``,
    ordered oldest-first for chronological rendering. ``has_more`` is
    true when older messages exist beyond the returned window."""

    messages: list[MessageRead]
    has_more: bool


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
