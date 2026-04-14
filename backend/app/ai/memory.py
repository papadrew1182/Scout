"""Safe family memory layer (Tier 5 F20).

Memories are persistent, editable preferences and planning defaults
— *not* a "save every chat turn" archive. Every memory has a review
lifecycle:

    proposed → active → archived

Only ``active`` memories are injected into prompts, and the
injection is bounded by ``settings.memory_inject_max_items`` and
``settings.memory_inject_max_chars_per_item``.

Sources that may write memories:

- ``parent_edit``       — explicit writes through the parent settings
                          surface.
- ``ai_proposed``       — a candidate written during an AI turn. Stays
                          ``proposed`` until a parent approves it.
- ``auto_structured``   — written as a side effect of an approved
                          structured flow (approved meal plan,
                          approved planner bundle). Lands directly as
                          ``active`` since the parent already approved
                          the originating action.

Memories are categorically distinct from:

- ``family_members.learning_notes``     — academic support context
- ``family_members.personality_notes``  — per-child tone/coaching

The distinctions matter for privacy: child surfaces never see
``scope='parent'`` memories, personality notes stay on the child
surface only, and learning notes stay keyed to the child.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Iterable

import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tier5 import FamilyMemory

logger = logging.getLogger("scout.ai.memory")


# Valid memory_type values — kept here (not as a DB CHECK constraint)
# so operators can add new types without a migration. The UI groups
# memories by type so the parent review page stays tidy.
MEMORY_TYPES = {
    "planning_default",    # grocery stores, batch-cook windows, etc.
    "meal_preference",     # staples, dislikes, dietary constraints
    "household_preference",  # reminder style, planning cadence
    "communication",       # family-level comm style; NOT personality_notes
    "other",
}


def record_parent_memory(
    db: Session,
    *,
    family_id: uuid.UUID,
    memory_type: str,
    scope: str,
    content: str,
    member_id: uuid.UUID | None = None,
    tags: list | None = None,
) -> FamilyMemory:
    """Direct parent write. Lands as ``active`` immediately."""
    if memory_type not in MEMORY_TYPES:
        memory_type = "other"
    row = FamilyMemory(
        family_id=family_id,
        member_id=member_id,
        memory_type=memory_type,
        scope=_coerce_scope(scope),
        content=content.strip(),
        tags=list(tags or []),
        source_kind="parent_edit",
        created_by_kind="parent",
        status="active",
        confidence=1.0,
    )
    db.add(row)
    db.flush()
    return row


def record_ai_proposed_memory(
    db: Session,
    *,
    family_id: uuid.UUID,
    memory_type: str,
    scope: str,
    content: str,
    source_conversation_id: uuid.UUID | None = None,
    confidence: float = 0.7,
    member_id: uuid.UUID | None = None,
    tags: list | None = None,
) -> FamilyMemory:
    """AI-proposed candidate. Stays ``proposed`` until a parent
    approves it — invisible to the prompt injector until then."""
    if memory_type not in MEMORY_TYPES:
        memory_type = "other"
    row = FamilyMemory(
        family_id=family_id,
        member_id=member_id,
        memory_type=memory_type,
        scope=_coerce_scope(scope),
        content=content.strip(),
        tags=list(tags or []),
        source_kind="ai_proposed",
        source_conversation_id=source_conversation_id,
        created_by_kind="ai",
        status="proposed",
        confidence=max(0.0, min(1.0, confidence)),
    )
    db.add(row)
    db.flush()
    return row


def record_auto_structured_memory(
    db: Session,
    *,
    family_id: uuid.UUID,
    memory_type: str,
    scope: str,
    content: str,
    source_conversation_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    tags: list | None = None,
) -> FamilyMemory | None:
    """Auto-memory from a structured flow the parent has already
    approved — e.g. an approved planner bundle or an approved meal
    plan. These land as ``active`` directly because approval already
    happened upstream.

    QA fix (test_qa BUG #4): the dedupe now compares a *normalized*
    form of the content — lowercase, whitespace-collapsed, trailing
    punctuation stripped — so trivial variants of the same sentence
    collapse to one row. The stored content stays exactly what the
    first writer provided; a parent who wants a different casing
    can edit the row."""
    if memory_type not in MEMORY_TYPES:
        memory_type = "other"
    normalized_content = content.strip()
    if not normalized_content:
        return None
    scope_value = _coerce_scope(scope)
    candidate_key = _normalize_for_dedupe(normalized_content)

    # Scan the small set of active rows in the same bucket and
    # compare on the normalized key. Family memory tables are
    # intentionally small — a full pass is fine.
    candidates = list(
        db.scalars(
            select(FamilyMemory)
            .where(FamilyMemory.family_id == family_id)
            .where(FamilyMemory.memory_type == memory_type)
            .where(FamilyMemory.scope == scope_value)
            .where(FamilyMemory.status == "active")
        ).all()
    )
    for existing in candidates:
        if _normalize_for_dedupe(existing.content or "") == candidate_key:
            existing.last_confirmed_at = datetime.now(pytz.UTC).replace(tzinfo=None)
            db.flush()
            return existing

    row = FamilyMemory(
        family_id=family_id,
        member_id=member_id,
        memory_type=memory_type,
        scope=scope_value,
        content=normalized_content,
        tags=list(tags or []),
        source_kind="auto_structured",
        source_conversation_id=source_conversation_id,
        created_by_kind="ai",
        status="active",
        confidence=0.9,
    )
    db.add(row)
    db.flush()
    return row


def list_family_memories(
    db: Session,
    *,
    family_id: uuid.UUID,
    status: str | None = None,
    memory_type: str | None = None,
) -> list[FamilyMemory]:
    stmt = (
        select(FamilyMemory)
        .where(FamilyMemory.family_id == family_id)
        .order_by(FamilyMemory.updated_at.desc())
    )
    if status:
        stmt = stmt.where(FamilyMemory.status == status)
    if memory_type:
        stmt = stmt.where(FamilyMemory.memory_type == memory_type)
    return list(db.scalars(stmt).all())


def approve_memory(
    db: Session, memory_id: uuid.UUID, family_id: uuid.UUID
) -> FamilyMemory | None:
    row = db.get(FamilyMemory, memory_id)
    if row is None or row.family_id != family_id:
        return None
    row.status = "active"
    row.last_confirmed_at = datetime.now(pytz.UTC).replace(tzinfo=None)
    db.flush()
    return row


def archive_memory(
    db: Session, memory_id: uuid.UUID, family_id: uuid.UUID
) -> FamilyMemory | None:
    row = db.get(FamilyMemory, memory_id)
    if row is None or row.family_id != family_id:
        return None
    row.status = "archived"
    db.flush()
    return row


def update_memory_content(
    db: Session,
    memory_id: uuid.UUID,
    family_id: uuid.UUID,
    *,
    content: str | None = None,
    memory_type: str | None = None,
    scope: str | None = None,
    tags: list | None = None,
) -> FamilyMemory | None:
    row = db.get(FamilyMemory, memory_id)
    if row is None or row.family_id != family_id:
        return None
    if content is not None:
        row.content = content.strip()
    if memory_type is not None:
        row.memory_type = (
            memory_type if memory_type in MEMORY_TYPES else "other"
        )
    if scope is not None:
        row.scope = _coerce_scope(scope)
    if tags is not None:
        row.tags = list(tags)
    row.last_confirmed_at = datetime.now(pytz.UTC).replace(tzinfo=None)
    db.flush()
    return row


def delete_memory(
    db: Session, memory_id: uuid.UUID, family_id: uuid.UUID
) -> bool:
    row = db.get(FamilyMemory, memory_id)
    if row is None or row.family_id != family_id:
        return False
    db.delete(row)
    db.flush()
    return True


# ---------------------------------------------------------------------------
# Prompt injection — bounded, deterministic, scope-aware
# ---------------------------------------------------------------------------


def build_memory_prompt_block(
    db: Session,
    *,
    family_id: uuid.UUID,
    surface: str,
    member_id: uuid.UUID | None = None,
    memory_types: Iterable[str] | None = None,
) -> str:
    """Return a short, deterministic prompt block listing ``active``
    memories relevant to the current surface. Empty string when
    nothing qualifies — callers append unconditionally.

    Scope rules:
      * ``child`` surface: only ``scope='family'`` memories and
        ``scope='child'`` memories whose ``member_id`` matches the
        current member. ``scope='parent'`` is NEVER leaked to kids.
      * ``parent`` / ``personal`` surface: ``scope='family'`` +
        ``scope='parent'``. Child-scoped memories skipped.

    Memory type filtering is optional: pass ``memory_types`` when
    the caller wants a narrow slice (e.g. meal planner only wants
    ``meal_preference`` + ``planning_default``)."""
    from app.config import settings

    stmt = (
        select(FamilyMemory)
        .where(FamilyMemory.family_id == family_id)
        .where(FamilyMemory.status == "active")
        .order_by(FamilyMemory.last_confirmed_at.desc())
    )
    if memory_types:
        stmt = stmt.where(FamilyMemory.memory_type.in_(list(memory_types)))

    rows = list(db.scalars(stmt).all())

    selected: list[FamilyMemory] = []
    for r in rows:
        if surface == "child":
            if r.scope == "parent":
                continue
            if r.scope == "child" and r.member_id != member_id:
                continue
        else:
            if r.scope == "child":
                continue
        selected.append(r)
        if len(selected) >= int(settings.memory_inject_max_items):
            break

    if not selected:
        return ""

    max_chars = int(settings.memory_inject_max_chars_per_item)
    lines = ["", "FAMILY MEMORY (preferences and planning defaults):"]
    for r in selected:
        content = (r.content or "").strip().replace("\n", " ")
        if len(content) > max_chars:
            content = content[: max_chars - 1].rstrip() + "…"
        lines.append(f"- [{r.memory_type}] {content}")
    lines.append(
        "Use these as background context; do not repeat them back to the user."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_scope(scope: str | None) -> str:
    if scope in ("parent", "family", "child"):
        return scope
    return "family"


def _normalize_for_dedupe(text: str) -> str:
    """Collapse trivial whitespace/case variants for near-duplicate
    matching. Lowercases, trims, joins runs of whitespace, and
    strips trailing sentence punctuation. Used ONLY for dedupe —
    never for prompt injection or display."""
    if not text:
        return ""
    collapsed = " ".join(text.lower().split())
    return collapsed.rstrip(".!?,;: ")
