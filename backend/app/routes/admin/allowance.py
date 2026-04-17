"""Admin routes for allowance / reward policy management.

Endpoints (all scoped to actor's family, require allowance.manage_config):

  GET  /admin/allowance/policies
       — list all active reward policies for the family

  PUT  /admin/allowance/policies/{member_id}
       — upsert a member's weekly_allowance reward policy
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import FamilyMember
from app.services import allowance_canonical

router = APIRouter(prefix="/admin/allowance", tags=["admin-allowance"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RewardPolicyItem(BaseModel):
    id: str
    family_member_id: str | None
    policy_key: str
    baseline_amount_cents: int
    payout_schedule: dict
    effective_from: str


class AllowancePolicyUpsertPayload(BaseModel):
    baseline_cents: int
    payout_schedule: str = "weekly"
    weekly_target_cents: int = 0
    effective_from: date | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_member(db: Session, member_id: uuid.UUID, actor: Actor) -> FamilyMember:
    member = db.get(FamilyMember, member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.family_id != actor.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Member not in your family")
    return member


def _to_item(policy) -> RewardPolicyItem:
    return RewardPolicyItem(
        id=str(policy.id),
        family_member_id=str(policy.family_member_id) if policy.family_member_id else None,
        policy_key=policy.policy_key,
        baseline_amount_cents=policy.baseline_amount_cents,
        payout_schedule=policy.payout_schedule,
        effective_from=policy.effective_from.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/policies", response_model=list[RewardPolicyItem])
def list_policies(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return all active weekly_allowance reward policies for the family.

    Requires allowance.manage_config.
    """
    actor.require_permission("allowance.manage_config")
    policies = allowance_canonical.get_family_reward_policies(db, actor.family_id)
    return [_to_item(p) for p in policies]


@router.put("/policies/{member_id}", response_model=RewardPolicyItem)
def upsert_policy(
    member_id: uuid.UUID,
    payload: AllowancePolicyUpsertPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Upsert a weekly_allowance reward policy for a specific member.

    Requires allowance.manage_config.
    """
    actor.require_permission("allowance.manage_config")
    _resolve_member(db, member_id, actor)

    policy = allowance_canonical.upsert_reward_policy(
        db,
        family_id=actor.family_id,
        member_id=member_id,
        baseline_cents=payload.baseline_cents,
        payout_schedule=payload.payout_schedule,
        weekly_target_cents=payload.weekly_target_cents,
        effective_from=payload.effective_from,
    )
    db.commit()
    return _to_item(policy)
