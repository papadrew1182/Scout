"""AI orchestration routes."""

import json
import logging
import uuid
from datetime import datetime, timedelta

import pytz
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import orchestrator
from app.ai.pricing import build_usage_report
from app.auth import Actor, get_current_actor
from app.config import settings
from app.database import get_db
from app.models.ai import AIConversation, AIMessage, AIToolAudit
from app.schemas.ai import (
    ArchiveOlderRequest,
    BriefRequest,
    BriefResponse,
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationPatchRequest,
    ConversationRead,
    ConversationStats,
    MessagePage,
    MessageRead,
    ResumableConversation,
    StapleMealsRequest,
    StapleMealsResponse,
    ToolAuditRead,
    WeeklyPlanRequest,
    WeeklyPlanResponse,
)
from app.services import ai_conversation_service

RESUME_FRESHNESS_MINUTES = 30

logger = logging.getLogger("scout.ai.routes")

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def ai_chat(
    body: ChatRequest,
    request: Request,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # noqa: public-route — any authenticated family member may chat; governance (ai.manage) controls admin toggles, not the chat surface itself
    trace_id = request.headers.get("x-scout-trace-id", "")
    if body.family_id:
        actor.require_family(body.family_id)

    logger.info(
        "ai_chat_start trace=%s member=%s surface=%s confirm=%s",
        trace_id, actor.member_id, body.surface,
        bool(body.confirm_tool),
    )
    try:
        result = orchestrator.chat(
            db=db,
            family_id=actor.family_id,
            member_id=actor.member_id,
            surface=body.surface,
            user_message=body.message,
            conversation_id=body.conversation_id,
            confirm_tool=body.confirm_tool.model_dump() if body.confirm_tool else None,
            intent=body.intent,
            attachment_path=body.attachment_path,
        )
        logger.info(
            "ai_chat_success trace=%s conversation=%s handoff=%s pending=%s",
            trace_id,
            result.get("conversation_id"),
            bool(result.get("handoff")),
            bool(result.get("pending_confirmation")),
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.error("ai_chat_fail trace=%s error=%s", trace_id, str(e)[:200])
        raise


@router.post("/chat/stream")
def ai_chat_stream(
    body: ChatRequest,
    request: Request,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # noqa: public-route — streaming variant of /chat; same access model (any authenticated family member)
    """Server-Sent Events version of /api/ai/chat.

    Streams the assistant's response incrementally. Confirm-tool resubmits
    are still sent to /api/ai/chat (non-streaming) because they are a
    single synchronous tool execution with no Claude round.
    """
    trace_id = request.headers.get("x-scout-trace-id", "")
    if body.family_id:
        actor.require_family(body.family_id)
    if body.confirm_tool is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm_tool is not supported on the streaming endpoint. "
                   "POST to /api/ai/chat instead.",
        )

    logger.info(
        "ai_chat_stream_start trace=%s member=%s surface=%s",
        trace_id, actor.member_id, body.surface,
    )

    def frames():
        try:
            for event in orchestrator.chat_stream(
                db=db,
                family_id=actor.family_id,
                member_id=actor.member_id,
                surface=body.surface,
                user_message=body.message,
                conversation_id=body.conversation_id,
                intent=body.intent,
            ):
                # One SSE frame per orchestrator event. Both lines are
                # required by the SSE spec — "data: <json>\n\n".
                yield f"data: {json.dumps(event)}\n\n"
            logger.info(
                "ai_chat_stream_success trace=%s",
                trace_id,
            )
        except Exception as e:
            logger.error("ai_chat_stream_fail trace=%s error=%s", trace_id, str(e)[:200])
            err = json.dumps({"type": "error", "message": str(e)[:400]})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Nginx/proxy hint to not buffer SSE
            "Connection": "keep-alive",
        },
    )


@router.post("/transcribe")
async def ai_transcribe(
    audio: UploadFile = File(...),
    actor: Actor = Depends(get_current_actor),
):
    # noqa: public-route — voice-input helper; available to any authenticated member; no family state mutated
    """Transcribe an uploaded audio blob (voice-input mic path).

    The frontend records via MediaRecorder (webm/opus on most browsers),
    POSTs the blob here, and feeds the returned text into the existing
    /api/ai/chat/stream endpoint. If no transcription key is configured
    this returns 501 so the frontend hides the mic button cleanly.
    """
    from app.ai.transcribe import transcribe_audio
    from app.config import settings

    if not settings.transcribe_available:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Transcription provider not configured.",
        )

    data = await audio.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio upload.",
        )
    if len(data) > settings.transcribe_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio upload exceeds {settings.transcribe_max_upload_bytes} bytes.",
        )

    try:
        result = transcribe_audio(data, audio.content_type or "audio/webm")
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(e),
        )
    except Exception as e:
        logger.error("transcribe_fail actor=%s err=%s", actor.member_id, str(e)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription provider failed.",
        )

    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "duration_ms": result.duration_ms,
    }


@router.post("/receipt")
async def ai_receipt(
    image: UploadFile = File(...),
    actor: Actor = Depends(get_current_actor),
):
    # noqa: public-route — read-only vision extraction; returns proposals, does NOT write grocery rows
    """Extract grocery items from a receipt photo.

    Vision-powered by Claude. Returns a list of proposals; does NOT
    write grocery rows. The frontend renders an editable review card
    and the user confirms each item, which then hits the existing
    ``create_grocery_item`` path (family-scoped, audited, etc.).
    """
    from app.ai.receipt import (
        ALLOWED_MIME,
        MAX_UPLOAD_BYTES,
        extract_items_from_receipt,
    )
    from app.config import settings

    if not settings.ai_available:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="AI provider not configured.",
        )

    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type: {content_type}. Use JPEG, PNG, or WEBP.",
        )

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {MAX_UPLOAD_BYTES} bytes.",
        )

    try:
        result = extract_items_from_receipt(data, content_type)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "receipt_extract_fail actor=%s err=%s",
            actor.member_id, str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vision provider failed.",
        )

    return {
        "items": [
            {
                "title": p.title,
                "quantity": p.quantity,
                "unit": p.unit,
                "category": p.category,
                "confidence": p.confidence,
            }
            for p in result.items
        ],
        "model": result.model,
        "tokens": {
            "input": result.input_tokens,
            "output": result.output_tokens,
        },
    }


@router.post("/brief/daily", response_model=BriefResponse)
def daily_brief(
    body: BriefRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # noqa: public-route — any authenticated family member may generate their own daily brief
    if body.family_id:
        actor.require_family(body.family_id)
    result = orchestrator.generate_daily_brief(db, actor.family_id, actor.member_id)
    return BriefResponse(**result)


@router.post("/plans/weekly", response_model=WeeklyPlanResponse)
def weekly_plan(
    body: WeeklyPlanRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # noqa: public-route — any authenticated family member may generate a weekly plan; plan approval requires meal_plan.approve
    if body.family_id:
        actor.require_family(body.family_id)
    result = orchestrator.generate_weekly_plan(db, actor.family_id, actor.member_id)
    return WeeklyPlanResponse(**result)


@router.post("/meals/staples", response_model=StapleMealsResponse)
def staple_meals(
    body: StapleMealsRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # noqa: public-route — suggestion endpoint; returns proposals only, no state written
    if body.family_id:
        actor.require_family(body.family_id)
    result = orchestrator.suggest_staple_meals(db, actor.family_id, actor.member_id)
    return StapleMealsResponse(**result)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    include_archived: bool = Query(False),
    pinned_first: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    family_id: uuid.UUID | None = Query(
        None,
        description="Optional legacy param. Listing is self-scoped by actor.",
    ),
    kind: str | None = Query(
        None,
        pattern="^(chat|tool|mixed|moderation)$",
        description="Optional filter by conversation_kind.",
    ),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Drawer / settings list of the caller's own conversations.

    Self-scoped by actor. `ended` conversations (user hit "New Chat")
    are hidden. `archived` conversations are hidden unless
    `include_archived=true`. Ordered by `last_active_at DESC`, with
    pinned rows floated to the top when `pinned_first=true`."""
    if family_id is not None:
        actor.require_family(family_id)
    rows = ai_conversation_service.list_conversations(
        db,
        family_member_id=actor.member_id,
        include_archived=include_archived,
        pinned_first=pinned_first,
        limit=limit,
        offset=offset,
    )
    if kind:
        rows = [r for r in rows if r.conversation_kind == kind]
    return rows


@router.get("/conversations/stats", response_model=ConversationStats)
def get_conversation_stats(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Self-scoped conversation counts for the settings history panel."""
    return ai_conversation_service.get_conversation_stats(
        db, family_member_id=actor.member_id
    )


@router.post("/conversations", response_model=ConversationRead)
def create_conversation(
    body: ConversationCreateRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Create a blank conversation for the 'New conversation' drawer
    affordance. Title derives from first_message when provided; the
    orchestrator upgrades the title on the first real user turn."""
    actor.require_permission("ai.manage_own_conversations")
    return ai_conversation_service.create_conversation(
        db,
        family_id=actor.family_id,
        family_member_id=actor.member_id,
        first_message=body.first_message,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
def patch_conversation(
    conversation_id: uuid.UUID,
    body: ConversationPatchRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Rename, archive-toggle, or pin-toggle own conversation. Unset
    fields are untouched. Ownership enforced at the service layer;
    non-owners get 404."""
    actor.require_permission("ai.manage_own_conversations")
    return ai_conversation_service.patch_conversation(
        db,
        conversation_id=conversation_id,
        actor=actor,
        title=body.title,
        status=body.status,
        is_pinned=body.is_pinned,
    )


@router.post("/conversations/archive-older-than")
def archive_older_than(
    body: ArchiveOlderRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Bulk archive own active conversations with no activity in the
    last `days` days. Archive-only; never deletes. Self-scoped."""
    actor.require_permission("ai.clear_own_history")
    archived = ai_conversation_service.bulk_archive_older_than(
        db,
        family_member_id=actor.member_id,
        days=body.days,
    )
    return {"archived_count": archived}


@router.get("/conversations/resumable", response_model=ResumableConversation)
def get_resumable_conversation(
    surface: str = Query("personal", pattern="^(personal|parent|child)$"),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return the most recent conversation that is SAFE to auto-resume
    for this actor on this surface, or a null envelope if none fit.

    Exclusion rules (all must pass):
      - status = 'active' (an 'ended' conversation was explicitly
        closed by the user via POST /conversations/{id}/end)
      - conversation_kind != 'moderation' (child was blocked — never
        auto-resume these; parent gets a separate alert anyway)
      - updated_at >= now - RESUME_FRESHNESS_MINUTES (30 min default)
      - last message is NOT a pending confirmation (we don't want the
        panel to silently pop back up on a dangerous in-flight write)
      - last assistant turn wasn't a moderation-blocked or error model
    """
    cutoff = datetime.now(pytz.UTC).replace(tzinfo=None) - timedelta(
        minutes=RESUME_FRESHNESS_MINUTES
    )
    candidates = list(
        db.scalars(
            select(AIConversation)
            .where(AIConversation.family_id == actor.family_id)
            .where(AIConversation.family_member_id == actor.member_id)
            .where(AIConversation.surface == surface)
            .where(AIConversation.status == "active")
            .where(AIConversation.conversation_kind != "moderation")
            .where(AIConversation.updated_at >= cutoff)
            .order_by(AIConversation.updated_at.desc())
            .limit(5)
        ).all()
    )

    for conv in candidates:
        last_msg = db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
            .limit(1)
        ).first()
        if not last_msg:
            continue

        # Gate: pending confirmation in-flight.
        if last_msg.role == "tool" and last_msg.tool_results:
            result = last_msg.tool_results.get("result") or {}
            if isinstance(result, dict) and result.get("confirmation_required"):
                continue

        # Gate: error or moderation-blocked terminal state.
        if last_msg.role == "assistant" and last_msg.model in (
            "moderation-blocked",
        ):
            continue

        # Pick first user message for the preview snippet — that's what
        # the UI should show as "you were asking about…".
        first_user = db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .where(AIMessage.role == "user")
            .order_by(AIMessage.created_at.asc(), AIMessage.id.asc())
            .limit(1)
        ).first()
        preview = (first_user.content or "") if first_user else ""
        if len(preview) > 120:
            preview = preview[:117] + "..."

        return ResumableConversation(
            conversation_id=conv.id,
            updated_at=conv.updated_at,
            preview=preview,
            kind=conv.conversation_kind,
        )

    return ResumableConversation(
        conversation_id=None, updated_at=None, preview=None, kind=None
    )


@router.post("/conversations/{conversation_id}/end")
def end_conversation(
    conversation_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # noqa: public-route — member can only end their own conversation (ownership checked below)
    """Mark a conversation ended so it drops out of the resumable set.

    Used by the 'Start new chat' affordance in ScoutPanel. The row is
    preserved for history/audit — only status flips. Idempotent."""
    conv = db.get(AIConversation, conversation_id)
    if (
        not conv
        or conv.family_id != actor.family_id
        or conv.family_member_id != actor.member_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    if conv.status == "active":
        conv.status = "ended"
        db.commit()
    return {"conversation_id": str(conv.id), "status": conv.status}


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    before_message_id: uuid.UUID | None = Query(None),
    family_id: uuid.UUID | None = Query(
        None, description="Optional legacy param. Access is self-scoped."
    ),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Paginated message read. Returns up to ``limit`` newest messages
    before ``before_message_id`` (or before now), ordered oldest-first
    for chronological rendering. ``has_more`` is true when older
    messages exist beyond the returned window.

    Ownership: caller must own the conversation (family_member_id match).
    This tightens the prior behavior, which only checked family-level
    access and allowed a sibling to read another sibling's thread."""
    if family_id is not None:
        actor.require_family(family_id)
    conv = db.get(AIConversation, conversation_id)
    if (
        conv is None
        or conv.family_id != actor.family_id
        or conv.family_member_id != actor.member_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    messages, has_more = ai_conversation_service.list_messages_paginated(
        db,
        conversation_id=conversation_id,
        limit=limit,
        before_message_id=before_message_id,
    )
    return MessagePage(messages=messages, has_more=has_more)


@router.get("/usage")
def ai_usage_report(
    days: int = Query(7, ge=1, le=90),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Parent-facing AI usage + approximate cost rollup.

    Aggregates ``ai_messages.token_usage`` across the family's
    conversations over the last N days (default 7). Returns per-day,
    per-model, and per-member breakdowns plus a soft-cap warning
    flag. Adult-only — kids shouldn't see the family's AI bill."""
    actor.require_permission("ai.manage")
    return build_usage_report(
        db,
        family_id=actor.family_id,
        days=days,
        soft_cap_usd=settings.ai_weekly_soft_cap_usd,
    )


@router.get("/audit", response_model=list[ToolAuditRead])
def list_audit(
    family_id: uuid.UUID = Query(...),
    tool_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    stmt = (
        select(AIToolAudit)
        .where(AIToolAudit.family_id == family_id)
    )
    if tool_name:
        stmt = stmt.where(AIToolAudit.tool_name == tool_name)
    stmt = stmt.order_by(AIToolAudit.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())
