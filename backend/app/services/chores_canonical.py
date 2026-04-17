"""Chores service for scout.routine_templates (canonical 022 tables).

Functions:
  get_member_chore_routines  — list RoutineTemplate rows for a member
  get_family_chore_routines  — list all RoutineTemplate rows for a family
                               grouped by owner_family_member_id
  upsert_chore_routine       — insert-or-update a single routine template
  delete_chore_routine       — hard-delete a routine template by id
"""

from __future__ import annotations

import uuid
from datetime import date as _date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical import RoutineTemplate
from app.models.foundation import FamilyMember


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_member_chore_routines(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
) -> list[RoutineTemplate]:
    """Return all RoutineTemplate rows owned by `member_id` in `family_id`."""
    return list(
        db.scalars(
            select(RoutineTemplate)
            .where(RoutineTemplate.family_id == family_id)
            .where(RoutineTemplate.owner_family_member_id == member_id)
            .order_by(RoutineTemplate.routine_key)
        ).all()
    )


def get_family_chore_routines(
    db: Session,
    family_id: uuid.UUID,
) -> list[RoutineTemplate]:
    """Return all RoutineTemplate rows for `family_id` ordered by member then key."""
    return list(
        db.scalars(
            select(RoutineTemplate)
            .where(RoutineTemplate.family_id == family_id)
            .order_by(
                RoutineTemplate.owner_family_member_id,
                RoutineTemplate.routine_key,
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def upsert_chore_routine(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    routine_key: str,
    label: str,
    recurrence: str = "daily",
    block_label: str = "Chores",
) -> RoutineTemplate:
    """Upsert a single RoutineTemplate.

    Matches on (family_id, routine_key, owner_family_member_id). If a row
    exists it is updated in-place; otherwise a new row is inserted.

    Returns the persisted RoutineTemplate (not yet committed — caller commits).
    """
    existing = db.scalars(
        select(RoutineTemplate)
        .where(RoutineTemplate.family_id == family_id)
        .where(RoutineTemplate.routine_key == routine_key)
        .where(RoutineTemplate.owner_family_member_id == member_id)
    ).first()

    if existing:
        existing.label = label
        existing.recurrence = recurrence
        existing.block_label = block_label
        db.flush()
        return existing

    template = RoutineTemplate(
        family_id=family_id,
        routine_key=routine_key,
        label=label,
        block_label=block_label,
        recurrence=recurrence,
        owner_family_member_id=member_id,
    )
    db.add(template)
    db.flush()
    return template


def delete_chore_routine(
    db: Session,
    family_id: uuid.UUID,
    routine_id: uuid.UUID,
) -> bool:
    """Delete a RoutineTemplate by id, scoped to family_id for safety.

    Returns True if a row was deleted, False if not found.
    """
    template = db.scalars(
        select(RoutineTemplate)
        .where(RoutineTemplate.id == routine_id)
        .where(RoutineTemplate.family_id == family_id)
    ).first()

    if template is None:
        return False

    db.delete(template)
    db.flush()
    return True
