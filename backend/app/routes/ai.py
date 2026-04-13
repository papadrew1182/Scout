"""AI orchestration routes."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    stmt = (
        select(AIConversation)
        .where(AIConversation.family_id == family_id)
        .where(AIConversation.family_member_id == actor.member_id)
        .order_by(AIConversation.updated_at.desc())
        .limit(20)
    )
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
