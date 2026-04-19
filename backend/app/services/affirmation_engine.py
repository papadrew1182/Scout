"""Affirmation selection engine and analytics.

select_affirmation()   — pick one affirmation for a member, log delivery
get_affirmation_analytics() — aggregate stats for admin dashboard
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, exists
from sqlalchemy.orm import Session

from app.models.affirmations import (
    Affirmation,
    AffirmationDeliveryLog,
    AffirmationFeedback,
)
from app.models.access import HouseholdRule, MemberConfig
from app.models.foundation import FamilyMember


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "enabled": True,
    "cooldown_days": 3,
    "max_repeat_window_days": 30,
    "weight_heart_boost": 1.5,
    "weight_preference_match": 1.3,
}


def _get_family_config(db: Session, family_id: uuid.UUID) -> dict:
    row = db.execute(
        select(HouseholdRule.rule_value).where(
            HouseholdRule.family_id == family_id,
            HouseholdRule.rule_key == "affirmations.config",
        )
    ).scalar()
    if row is None:
        return dict(_DEFAULT_CONFIG)
    merged = dict(_DEFAULT_CONFIG)
    merged.update(row)
    return merged


def _get_member_prefs(db: Session, member_id: uuid.UUID) -> dict:
    row = db.execute(
        select(MemberConfig.value).where(
            MemberConfig.family_member_id == member_id,
            MemberConfig.key == "affirmations.preferences",
        )
    ).scalar()
    return row or {}


# ---------------------------------------------------------------------------
# Selection engine
# ---------------------------------------------------------------------------

def select_affirmation(
    db: Session,
    member_id: uuid.UUID,
    family_id: uuid.UUID,
    surface: str = "today",
) -> dict | None:
    """Select one affirmation for the member. Returns dict or None."""

    config = _get_family_config(db, family_id)
    if not config.get("enabled", True):
        return None

    prefs = _get_member_prefs(db, member_id)
    if not prefs.get("enabled", True):
        return None

    member = db.get(FamilyMember, member_id)
    if member is None:
        return None

    eligible = _filter_eligible(db, member, config)
    if not eligible:
        eligible = _filter_eligible(db, member, config, relax_cooldown=True)
    if not eligible:
        return None

    scored = _score(db, eligible, member_id, prefs, config)
    selected = _weighted_pick(scored)

    now = datetime.now(timezone.utc)
    delivery = AffirmationDeliveryLog(
        family_member_id=member_id,
        affirmation_id=selected.id,
        surfaced_at=now,
        surfaced_in=surface,
    )
    db.add(delivery)
    db.flush()

    return {
        "affirmation": {
            "id": str(selected.id),
            "text": selected.text,
            "category": selected.category,
            "tone": selected.tone,
        },
        "delivered_at": now.isoformat(),
        "delivery_id": str(delivery.id),
    }


def _audience_types_for_role(role: str) -> list[str]:
    if role == "adult":
        return ["general", "family", "parent"]
    return ["general", "family", "child"]


def _filter_eligible(
    db: Session,
    member: FamilyMember,
    config: dict,
    relax_cooldown: bool = False,
) -> list[Affirmation]:
    now = datetime.now(timezone.utc)
    cooldown_days = config.get("cooldown_days", 3)
    if relax_cooldown:
        cooldown_days = max(1, cooldown_days // 2)
    cooldown_cutoff = now - timedelta(days=cooldown_days)
    repeat_window = now - timedelta(days=config.get("max_repeat_window_days", 30))

    audiences = _audience_types_for_role(member.role)

    # Subquery: affirmation IDs thumbs-downed without a later reshow
    thumbs_down_sub = (
        select(AffirmationFeedback.affirmation_id)
        .where(
            AffirmationFeedback.family_member_id == member.id,
            AffirmationFeedback.reaction_type == "thumbs_down",
        )
        .correlate()
        .subquery()
    )
    reshow_sub = (
        select(AffirmationFeedback.affirmation_id)
        .where(
            AffirmationFeedback.family_member_id == member.id,
            AffirmationFeedback.reaction_type == "reshow",
            AffirmationFeedback.created_at > (
                select(func.max(AffirmationFeedback.created_at)).where(
                    AffirmationFeedback.family_member_id == member.id,
                    AffirmationFeedback.reaction_type == "thumbs_down",
                    AffirmationFeedback.affirmation_id == AffirmationFeedback.affirmation_id,
                ).correlate(AffirmationFeedback).scalar_subquery()
            ),
        )
        .correlate()
        .subquery()
    )

    # Subquery: recently delivered IDs within cooldown
    recent_delivery_sub = (
        select(AffirmationDeliveryLog.affirmation_id)
        .where(
            AffirmationDeliveryLog.family_member_id == member.id,
            AffirmationDeliveryLog.surfaced_at >= cooldown_cutoff,
        )
        .subquery()
    )

    # Subquery: delivered more than once within repeat window
    repeat_sub = (
        select(AffirmationDeliveryLog.affirmation_id)
        .where(
            AffirmationDeliveryLog.family_member_id == member.id,
            AffirmationDeliveryLog.surfaced_at >= repeat_window,
        )
        .group_by(AffirmationDeliveryLog.affirmation_id)
        .having(func.count() > 1)
        .subquery()
    )

    q = (
        select(Affirmation)
        .where(
            Affirmation.active == True,  # noqa: E712
            Affirmation.audience_type.in_(audiences),
            Affirmation.id.not_in(select(thumbs_down_sub)),
            Affirmation.id.not_in(select(recent_delivery_sub)),
            Affirmation.id.not_in(select(repeat_sub)),
        )
    )
    # Allow back affirmations that were reshowed after thumbs_down
    # This is handled by the reshow check — but the simple NOT IN thumbs_down
    # is conservative. We refine: exclude thumbs_down UNLESS reshow exists later.
    # For v1 simplicity, use a Python post-filter instead of complex SQL.

    candidates = list(db.execute(q).scalars().all())

    # Post-filter: restore reshowed affirmations
    if candidates:
        return candidates

    # If no candidates, try including thumbs-downed ones that were reshowed
    q_with_reshowed = (
        select(Affirmation)
        .where(
            Affirmation.active == True,  # noqa: E712
            Affirmation.audience_type.in_(audiences),
            Affirmation.id.not_in(select(recent_delivery_sub)),
            Affirmation.id.not_in(select(repeat_sub)),
        )
    )
    all_candidates = list(db.execute(q_with_reshowed).scalars().all())

    # Filter out thumbs-downed that don't have a later reshow
    td_ids = set(
        db.execute(
            select(AffirmationFeedback.affirmation_id).where(
                AffirmationFeedback.family_member_id == member.id,
                AffirmationFeedback.reaction_type == "thumbs_down",
            )
        ).scalars().all()
    )
    reshow_ids = set()
    if td_ids:
        for aff_id in td_ids:
            td_time = db.execute(
                select(func.max(AffirmationFeedback.created_at)).where(
                    AffirmationFeedback.family_member_id == member.id,
                    AffirmationFeedback.affirmation_id == aff_id,
                    AffirmationFeedback.reaction_type == "thumbs_down",
                )
            ).scalar()
            rs_time = db.execute(
                select(func.max(AffirmationFeedback.created_at)).where(
                    AffirmationFeedback.family_member_id == member.id,
                    AffirmationFeedback.affirmation_id == aff_id,
                    AffirmationFeedback.reaction_type == "reshow",
                )
            ).scalar()
            if rs_time and rs_time > td_time:
                reshow_ids.add(aff_id)

    return [a for a in all_candidates if a.id not in td_ids or a.id in reshow_ids]


def _score(
    db: Session,
    candidates: list[Affirmation],
    member_id: uuid.UUID,
    prefs: dict,
    config: dict,
) -> list[tuple[Affirmation, float]]:
    heart_boost = config.get("weight_heart_boost", 1.5)
    pref_boost = config.get("weight_preference_match", 1.3)

    # Get categories this member has hearted
    hearted_categories = set(
        db.execute(
            select(Affirmation.category)
            .join(AffirmationFeedback, AffirmationFeedback.affirmation_id == Affirmation.id)
            .where(
                AffirmationFeedback.family_member_id == member_id,
                AffirmationFeedback.reaction_type == "heart",
            )
        ).scalars().all()
    )

    # Get affirmation IDs previously delivered to this member
    delivered_ids = set(
        db.execute(
            select(AffirmationDeliveryLog.affirmation_id).where(
                AffirmationDeliveryLog.family_member_id == member_id,
            )
        ).scalars().all()
    )

    pref_tones = set(prefs.get("preferred_tones", []))
    pref_philosophies = set(prefs.get("preferred_philosophies", []))

    scored = []
    for aff in candidates:
        score = 1.0

        if aff.category in hearted_categories:
            score *= heart_boost

        if (aff.tone and aff.tone in pref_tones) or (aff.philosophy and aff.philosophy in pref_philosophies):
            score *= pref_boost

        if aff.id in delivered_ids:
            score *= 0.5

        scored.append((aff, score))

    return scored


def _weighted_pick(scored: list[tuple[Affirmation, float]]) -> Affirmation:
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:5]
    weights = [s for _, s in top]
    choices = [a for a, _ in top]
    return random.choices(choices, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_affirmation_analytics(db: Session, family_id: uuid.UUID) -> dict:
    """Aggregate affirmation analytics for the family."""

    # Total affirmations and active count (family-agnostic — library is shared)
    total = db.execute(select(func.count()).select_from(Affirmation)).scalar() or 0
    active_count = db.execute(
        select(func.count()).select_from(Affirmation).where(Affirmation.active == True)  # noqa: E712
    ).scalar() or 0

    # Delivery count — scoped to family members
    family_member_ids_q = select(FamilyMember.id).where(FamilyMember.family_id == family_id)

    total_deliveries = db.execute(
        select(func.count()).select_from(AffirmationDeliveryLog).where(
            AffirmationDeliveryLog.family_member_id.in_(family_member_ids_q)
        )
    ).scalar() or 0

    # Reaction counts
    reactions = {"heart": 0, "thumbs_down": 0, "skip": 0, "reshow": 0}
    rows = db.execute(
        select(AffirmationFeedback.reaction_type, func.count())
        .where(AffirmationFeedback.family_member_id.in_(family_member_ids_q))
        .group_by(AffirmationFeedback.reaction_type)
    ).all()
    for rtype, cnt in rows:
        if rtype in reactions:
            reactions[rtype] = cnt

    # Most liked (top 5 by heart count)
    most_liked_q = (
        select(
            Affirmation.id, Affirmation.text,
            func.count().label("hearts"),
        )
        .join(AffirmationFeedback, AffirmationFeedback.affirmation_id == Affirmation.id)
        .where(
            AffirmationFeedback.reaction_type == "heart",
            AffirmationFeedback.family_member_id.in_(family_member_ids_q),
        )
        .group_by(Affirmation.id, Affirmation.text)
        .order_by(func.count().desc())
        .limit(5)
    )
    most_liked = [
        {"id": str(r.id), "text": r.text, "hearts": r.hearts}
        for r in db.execute(most_liked_q).all()
    ]

    # Most rejected (top 5 by thumbs_down count)
    most_rejected_q = (
        select(
            Affirmation.id, Affirmation.text,
            func.count().label("thumbs_down"),
        )
        .join(AffirmationFeedback, AffirmationFeedback.affirmation_id == Affirmation.id)
        .where(
            AffirmationFeedback.reaction_type == "thumbs_down",
            AffirmationFeedback.family_member_id.in_(family_member_ids_q),
        )
        .group_by(Affirmation.id, Affirmation.text)
        .order_by(func.count().desc())
        .limit(5)
    )
    most_rejected = [
        {"id": str(r.id), "text": r.text, "thumbs_down": r.thumbs_down}
        for r in db.execute(most_rejected_q).all()
    ]

    # Stale — active affirmations never delivered or not delivered in 30+ days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stale_q = (
        select(Affirmation.id, Affirmation.text,
               func.max(AffirmationDeliveryLog.surfaced_at).label("last_delivered"))
        .outerjoin(AffirmationDeliveryLog, AffirmationDeliveryLog.affirmation_id == Affirmation.id)
        .where(Affirmation.active == True)  # noqa: E712
        .group_by(Affirmation.id, Affirmation.text)
        .having(
            func.max(AffirmationDeliveryLog.surfaced_at).is_(None)
            | (func.max(AffirmationDeliveryLog.surfaced_at) < thirty_days_ago)
        )
        .limit(10)
    )
    stale = [
        {
            "id": str(r.id),
            "text": r.text,
            "last_delivered": r.last_delivered.isoformat() if r.last_delivered else None,
        }
        for r in db.execute(stale_q).all()
    ]

    # Per audience breakdown
    per_audience_rows = db.execute(
        select(Affirmation.audience_type, func.count())
        .where(Affirmation.active == True)  # noqa: E712
        .group_by(Affirmation.audience_type)
    ).all()
    per_audience = {r[0]: r[1] for r in per_audience_rows}

    return {
        "total_affirmations": total,
        "active_count": active_count,
        "total_deliveries": total_deliveries,
        "reactions": reactions,
        "most_liked": most_liked,
        "most_rejected": most_rejected,
        "stale": stale,
        "per_audience": per_audience,
    }
