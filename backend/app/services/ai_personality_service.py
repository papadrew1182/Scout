"""Per-member personality config service (Sprint 04 Phase 2).

Reads merge stored `member_config['ai.personality']` on top of tier
canonical defaults from `app.ai.personality_defaults`. Writes validate
enum membership and free-text length before upserting.

A member with no stored row still returns a full merged config — no
backfill migration needed when a new member is added.

Ownership / tier lookup helpers: `get_member_tier_name(db, member_id)`
is the mapping between a family_member and their role_tiers row,
reflecting the actual canonical uppercase names (PRIMARY_PARENT etc.).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException, status as http_status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import personality_defaults

logger = logging.getLogger("scout.ai.personality")

MEMBER_CONFIG_KEY = "ai.personality"


def _validate_enum(field: str, value: Any, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} must be one of {list(allowed)}",
        )


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a PATCH payload. Returns a sanitized dict containing
    only allowed keys with validated values. Raises 422 on any
    unknown key or invalid enum / length."""
    unknown = set(payload.keys()) - personality_defaults.ALLOWED_KEYS
    if unknown:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown personality keys: {sorted(unknown)}",
        )
    clean: dict[str, Any] = {}
    if "tone" in payload:
        _validate_enum("tone", payload["tone"], personality_defaults.TONE_OPTIONS)
        clean["tone"] = payload["tone"]
    if "vocabulary_level" in payload:
        _validate_enum(
            "vocabulary_level",
            payload["vocabulary_level"],
            personality_defaults.VOCAB_OPTIONS,
        )
        clean["vocabulary_level"] = payload["vocabulary_level"]
    if "formality" in payload:
        _validate_enum(
            "formality", payload["formality"], personality_defaults.FORMALITY_OPTIONS
        )
        clean["formality"] = payload["formality"]
    if "humor" in payload:
        _validate_enum("humor", payload["humor"], personality_defaults.HUMOR_OPTIONS)
        clean["humor"] = payload["humor"]
    if "proactivity" in payload:
        _validate_enum(
            "proactivity",
            payload["proactivity"],
            personality_defaults.PROACTIVITY_OPTIONS,
        )
        clean["proactivity"] = payload["proactivity"]
    if "verbosity" in payload:
        _validate_enum(
            "verbosity", payload["verbosity"], personality_defaults.VERBOSITY_OPTIONS
        )
        clean["verbosity"] = payload["verbosity"]
    if "notes_to_self" in payload:
        v = payload["notes_to_self"]
        if v is None:
            v = ""
        if not isinstance(v, str):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="notes_to_self must be a string",
            )
        clean["notes_to_self"] = v.strip()[: personality_defaults.NOTES_MAX]
    if "role_hints" in payload:
        v = payload["role_hints"]
        if v is None:
            v = ""
        if not isinstance(v, str):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="role_hints must be a string",
            )
        clean["role_hints"] = v.strip()[: personality_defaults.ROLE_HINTS_MAX]
    return clean


_ROLE_FALLBACK_TO_TIER: dict[str, str] = {
    "adult": "PRIMARY_PARENT",
    "child": "CHILD",
}


def get_member_tier_name(
    db: Session, family_member_id: uuid.UUID
) -> str | None:
    """Return the canonical role_tiers.name (UPPERCASE convention) for a
    member. Mirrors the algorithm in app.services.permissions:
      1. role_tier_overrides row wins if present
      2. Otherwise fall back to family_members.role (adult → PRIMARY_PARENT,
         child → CHILD)."""
    row = db.execute(
        text(
            """
            SELECT rt.name
            FROM role_tier_overrides rto
            JOIN role_tiers rt ON rt.id = rto.role_tier_id
            WHERE rto.family_member_id = :member_id
            LIMIT 1
            """
        ),
        {"member_id": family_member_id},
    ).first()
    if row:
        return row[0]
    # Fallback to the member's legacy role field
    legacy = db.execute(
        text("SELECT role FROM family_members WHERE id = :member_id"),
        {"member_id": family_member_id},
    ).first()
    if not legacy:
        return None
    return _ROLE_FALLBACK_TO_TIER.get(legacy[0])


def get_stored_config(
    db: Session, family_member_id: uuid.UUID
) -> dict[str, Any] | None:
    """Return the stored personality config for a member (raw
    member_config.value), or None if no row exists."""
    row = db.execute(
        text(
            """
            SELECT value FROM member_config
            WHERE family_member_id = :member_id AND key = :key
            """
        ),
        {"member_id": family_member_id, "key": MEMBER_CONFIG_KEY},
    ).first()
    return row[0] if row else None


def get_resolved_config(
    db: Session, family_member_id: uuid.UUID
) -> dict[str, Any]:
    """Return the merged personality config: stored overlaid on tier
    defaults. Callers use this for both API reads and prompt
    composition."""
    tier = get_member_tier_name(db, family_member_id)
    stored = get_stored_config(db, family_member_id)
    return personality_defaults.merge_over_defaults(stored, tier)


def upsert_personality(
    db: Session,
    family_member_id: uuid.UUID,
    payload: dict[str, Any],
    updated_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Validate and merge the PATCH payload into the member's stored
    config. Returns the merged resolved config (stored + tier defaults)
    after the write."""
    clean = validate_payload(payload)
    if not clean:
        # No-op PATCH. Still return current resolved config.
        return get_resolved_config(db, family_member_id)

    existing = get_stored_config(db, family_member_id) or {}
    next_stored: dict[str, Any] = {**existing, **clean}

    db.execute(
        text(
            """
            INSERT INTO member_config (family_member_id, key, value, updated_by)
            VALUES (:member_id, :key, CAST(:value AS JSONB), :updated_by)
            ON CONFLICT (family_member_id, key)
            DO UPDATE SET value = EXCLUDED.value,
                          updated_by = EXCLUDED.updated_by,
                          updated_at = NOW()
            """
        ),
        {
            "member_id": family_member_id,
            "key": MEMBER_CONFIG_KEY,
            "value": __import__("json").dumps(next_stored),
            "updated_by": updated_by,
        },
    )
    db.commit()
    logger.info(
        "personality_upserted member=%s keys=%s", family_member_id, sorted(clean.keys())
    )
    return get_resolved_config(db, family_member_id)


def build_personality_preamble(resolved: dict[str, Any]) -> str:
    """Compose a short system-prompt preamble describing the voice
    Scout should use. Keep it compact — this rides on every chat turn.

    Deterministic output so prompt-composition tests can assert exact
    substrings per enum value. No template parameters beyond the
    resolved config."""
    lines = ["## Voice profile for this member"]
    tone = resolved.get("tone", "warm")
    vocab = resolved.get("vocabulary_level", "standard")
    formality = resolved.get("formality", "casual")
    humor = resolved.get("humor", "light")
    verbosity = resolved.get("verbosity", "standard")
    lines.append(f"- Tone: {tone}")
    lines.append(f"- Vocabulary level: {vocab}")
    lines.append(f"- Formality: {formality}")
    lines.append(f"- Humor: {humor}")
    lines.append(f"- Default verbosity: {verbosity}")
    notes = (resolved.get("notes_to_self") or "").strip()
    if notes:
        lines.append(f"- Member notes: {notes}")
    role_hints = (resolved.get("role_hints") or "").strip()
    if role_hints:
        lines.append(f"- Role context: {role_hints}")
    # proactivity is intentionally absent from the preamble; it has
    # no runtime effect until Sprint 05 ships the nudges engine.
    return "\n".join(lines)
