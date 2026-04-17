"""Allowance service for scout.reward_policies (canonical 022 tables).

Functions:
  get_member_reward_policy  — fetch the active RewardPolicy for a member
  get_family_reward_policies — fetch all active RewardPolicy rows for a family
  upsert_reward_policy       — insert-or-update a member's reward policy
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical import RewardPolicy


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_member_reward_policy(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    policy_key: str = "weekly_allowance",
) -> RewardPolicy | None:
    """Return the most-recently-effective RewardPolicy for a member, or None."""
    return db.scalars(
        select(RewardPolicy)
        .where(RewardPolicy.family_id == family_id)
        .where(RewardPolicy.family_member_id == member_id)
        .where(RewardPolicy.policy_key == policy_key)
        .where(RewardPolicy.effective_from <= date.today())
        .where(
            (RewardPolicy.effective_until == None)  # noqa: E711
            | (RewardPolicy.effective_until >= date.today())
        )
        .order_by(RewardPolicy.effective_from.desc())
        .limit(1)
    ).first()


def get_family_reward_policies(
    db: Session,
    family_id: uuid.UUID,
    policy_key: str = "weekly_allowance",
) -> list[RewardPolicy]:
    """Return all active RewardPolicy rows for a family ordered by member."""
    return list(
        db.scalars(
            select(RewardPolicy)
            .where(RewardPolicy.family_id == family_id)
            .where(RewardPolicy.policy_key == policy_key)
            .where(RewardPolicy.effective_from <= date.today())
            .where(
                (RewardPolicy.effective_until == None)  # noqa: E711
                | (RewardPolicy.effective_until >= date.today())
            )
            .order_by(RewardPolicy.family_member_id, RewardPolicy.effective_from.desc())
        ).all()
    )


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def upsert_reward_policy(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    baseline_cents: int,
    payout_schedule: str = "weekly",
    weekly_target_cents: int = 0,
    policy_key: str = "weekly_allowance",
    effective_from: date | None = None,
) -> RewardPolicy:
    """Upsert a RewardPolicy for a member.

    Matches on (family_id, family_member_id, policy_key, effective_from).
    If effective_from is None it defaults to today. If a matching row exists
    it is updated in-place; otherwise a new row is inserted.

    Returns the persisted RewardPolicy (not yet committed — caller commits).
    """
    eff_date = effective_from or date.today()

    existing = db.scalars(
        select(RewardPolicy)
        .where(RewardPolicy.family_id == family_id)
        .where(RewardPolicy.family_member_id == member_id)
        .where(RewardPolicy.policy_key == policy_key)
        .where(RewardPolicy.effective_from == eff_date)
    ).first()

    schedule_json = {
        "schedule": payout_schedule,
        "weekly_target_cents": weekly_target_cents,
    }

    if existing:
        existing.baseline_amount_cents = baseline_cents
        existing.payout_schedule = schedule_json
        db.flush()
        return existing

    policy = RewardPolicy(
        family_id=family_id,
        family_member_id=member_id,
        policy_key=policy_key,
        baseline_amount_cents=baseline_cents,
        payout_schedule=schedule_json,
        effective_from=eff_date,
    )
    db.add(policy)
    db.flush()
    return policy
