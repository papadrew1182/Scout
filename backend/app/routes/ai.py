"""AI orchestration routes."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import orchestrator
from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.ai import AIConversation, AIMessage, AIToolAudit
from app.schemas.ai import (
    BriefRequest,
    BriefResponse,
    ChatRequest,
    ChatResponse,
    ConversationRead,
    MessageRead,
    StapleMealsRequest,
    StapleMealsResponse,
    ToolAuditRead,
    WeeklyPlanRequest,
    WeeklyPlanResponse,
)

logger = logging.getLogger("scout.ai.routes")

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def ai_chat(
    body: ChatRequest,
    request: Request,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
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
    if body.family_id:
        actor.require_family(body.family_id)
    result = orchestrator.suggest_staple_meals(db, actor.family_id, actor.member_id)
    return StapleMealsResponse(**result)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    family_id: uuid.UUID = Query(...),
    kind: str | None = Query(
        None,
        pattern="^(chat|tool|mixed|moderation)$",
        description="Filter by conversation_kind",
    ),
    limit: int = Query(20, ge=1, le=100),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    stmt = (
        select(AIConversation)
        .where(AIConversation.family_id == family_id)
        .where(AIConversation.family_member_id == actor.member_id)
        .order_by(AIConversation.updated_at.desc())
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(AIConversation.conversation_kind == kind)
    return list(db.scalars(stmt).all())


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: uuid.UUID,
    family_id: uuid.UUID = Query(...),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    conv = db.get(AIConversation, conversation_id)
    if not conv or conv.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at)
    )
    return list(db.scalars(stmt).all())


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
