"""Services for AI conversation list, resume, and archive management.

Sprint 04 Phase 1. Backs the new drawer / settings surfaces that let a
family member browse, rename, archive, and pin their own conversation
history. The existing ``GET /api/ai/conversations/resumable`` endpoint
is unchanged — its 30-minute freshness window plus pending-confirmation
and moderation safety gates still govern auto-resume of an in-flight
thread. This service only backs the user-managed list.

Status model:
- ``active``   live thread, eligible for auto-resume
- ``ended``    user hit "New Chat" on an active thread (existing)
- ``archived`` user explicitly archived the thread via the drawer

All mutating functions enforce ownership at the service layer. The
caller's ``Actor`` is compared against the conversation's family_id
and family_member_id; mismatches raise 404 so callers never learn
another member has a conversation with the given id.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import Actor
from app.models.ai import AIConversation, AIMessage

logger = logging.getLogger("scout.ai.conversations")

_TITLE_MAX = 60
_RENAME_MAX = 200
_WS_RE = re.compile(r"\s+")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_title(first_user_message: str | None) -> str:
    """First 60 trimmed characters after whitespace normalization.
    Falls back to 'New conversation' when the message is missing or
    blank so every conversation always has a non-null display title."""
    if not first_user_message:
        return "New conversation"
    compact = _WS_RE.sub(" ", first_user_message).strip()
    if not compact:
        return "New conversation"
    return compact[:_TITLE_MAX]


def _assert_ownership(conv: AIConversation | None, actor: Actor) -> AIConversation:
    if (
        conv is None
        or conv.family_id != actor.family_id
        or conv.family_member_id != actor.member_id
    ):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conv


def list_conversations(
    db: Session,
    family_member_id: uuid.UUID,
    include_archived: bool = False,
    limit: int = 20,
    offset: int = 0,
    pinned_first: bool = True,
) -> list[AIConversation]:
    """List the caller's conversations for the drawer. Excludes 'ended'
    conversations by default (those were explicitly "New chat"-ed away
    from). Optional include_archived adds 'archived' rows; 'active' are
    always included."""
    stmt = (
        select(AIConversation)
        .where(AIConversation.family_member_id == family_member_id)
        .where(AIConversation.status != "ended")
    )
    if not include_archived:
        stmt = stmt.where(AIConversation.status == "active")

    if pinned_first:
        stmt = stmt.order_by(
            AIConversation.is_pinned.desc(),
            AIConversation.last_active_at.desc(),
        )
    else:
        stmt = stmt.order_by(AIConversation.last_active_at.desc())

    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def get_conversation_stats(
    db: Session, family_member_id: uuid.UUID
) -> dict[str, int]:
    """Counts for the Conversation history settings panel. Excludes
    'ended' from the total so the numbers match what the drawer shows."""
    total = db.scalar(
        select(func.count(AIConversation.id))
        .where(AIConversation.family_member_id == family_member_id)
        .where(AIConversation.status != "ended")
    ) or 0
    active = db.scalar(
        select(func.count(AIConversation.id))
        .where(AIConversation.family_member_id == family_member_id)
        .where(AIConversation.status == "active")
    ) or 0
    archived = db.scalar(
        select(func.count(AIConversation.id))
        .where(AIConversation.family_member_id == family_member_id)
        .where(AIConversation.status == "archived")
    ) or 0
    return {
        "total_count": int(total),
        "active_count": int(active),
        "archived_count": int(archived),
    }


def create_conversation(
    db: Session,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID,
    first_message: str | None = None,
) -> AIConversation:
    """Create an empty conversation for the drawer's 'New conversation'
    affordance. Title is derived from first_message when provided. The
    orchestrator will upgrade a null / 'New conversation' title on the
    first real user turn (see maybe_upgrade_title)."""
    conv = AIConversation(
        family_id=family_id,
        family_member_id=family_member_id,
        surface="personal",
        status="active",
        conversation_kind="chat",
        title=generate_title(first_message),
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def patch_conversation(
    db: Session,
    conversation_id: uuid.UUID,
    actor: Actor,
    title: str | None = None,
    status: str | None = None,
    is_pinned: bool | None = None,
) -> AIConversation:
    """Combined rename / archive-toggle / pin-toggle. Unset fields are
    left alone. status is limited to 'active' or 'archived'; to end a
    conversation use the existing POST /conversations/{id}/end route."""
    conv = _assert_ownership(db.get(AIConversation, conversation_id), actor)
    if title is not None:
        trimmed = title.strip()
        conv.title = trimmed[:_RENAME_MAX] if trimmed else None
    if status is not None:
        if status not in ("active", "archived"):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="status must be 'active' or 'archived'",
            )
        conv.status = status
    if is_pinned is not None:
        conv.is_pinned = is_pinned
    db.commit()
    db.refresh(conv)
    return conv


def bulk_archive_older_than(
    db: Session, family_member_id: uuid.UUID, days: int
) -> int:
    """Archive all active conversations for the caller that have had
    no user/assistant activity in ``days`` days. Returns the number of
    rows archived. Archive-only: never deletes."""
    cutoff = _utcnow() - timedelta(days=days)
    rows = list(
        db.scalars(
            select(AIConversation)
            .where(AIConversation.family_member_id == family_member_id)
            .where(AIConversation.status == "active")
            .where(AIConversation.last_active_at < cutoff)
        ).all()
    )
    for conv in rows:
        conv.status = "archived"
    if rows:
        db.commit()
    return len(rows)


def list_messages_paginated(
    db: Session,
    conversation_id: uuid.UUID,
    limit: int = 50,
    before_message_id: uuid.UUID | None = None,
) -> tuple[list[AIMessage], bool]:
    """Return up to ``limit`` newest messages before ``before_message_id``
    (or before now), reversed to oldest-first for UI rendering. Uses
    ``(created_at, id)`` as the pagination key to be deterministic
    across messages that share the same clock_timestamp() microsecond."""
    stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
    )
    if before_message_id is not None:
        cursor = db.get(AIMessage, before_message_id)
        if cursor is not None:
            stmt = stmt.where(
                (AIMessage.created_at < cursor.created_at)
                | (
                    (AIMessage.created_at == cursor.created_at)
                    & (AIMessage.id < cursor.id)
                )
            )
    rows = list(db.scalars(stmt.limit(limit + 1)).all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    rows.reverse()
    return rows, has_more


def bump_last_active(
    db: Session, conversation_id: uuid.UUID, at: datetime | None = None
) -> None:
    """Called by the orchestrator after a user or assistant turn is
    persisted. Writes only last_active_at so metadata mutations
    (rename/pin/archive) continue to bump updated_at alone via the
    existing trigger."""
    ts = at or _utcnow()
    db.execute(
        update(AIConversation)
        .where(AIConversation.id == conversation_id)
        .values(last_active_at=ts)
    )


def maybe_upgrade_title(
    db: Session, conversation_id: uuid.UUID, first_user_message: str
) -> None:
    """On the first real user turn, set the title from the message if
    the current title is null or the 'New conversation' placeholder.
    No-op otherwise — once the user has renamed, we respect it.

    Does not commit; the caller's transaction carries the change. This
    lets the orchestrator batch the title upgrade into the same commit
    as the user-message persist."""
    conv = db.get(AIConversation, conversation_id)
    if conv is None:
        return
    if conv.title is None or conv.title == "New conversation":
        conv.title = generate_title(first_user_message)
