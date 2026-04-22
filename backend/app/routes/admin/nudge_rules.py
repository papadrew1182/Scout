"""Admin CRUD for nudge rules (Sprint 05 Phase 4 Task 6).

Five routes under /api/admin/nudges/rules, all gated by
nudges.configure (PARENT + PRIMARY_PARENT per migration 051):

  GET    /rules                      - list the caller's family rules
  POST   /rules                      - create; validates template_sql
                                       via validate_rule_sql and stores
                                       canonical_sql
  PATCH  /rules/{id}                 - update; re-validates on any
                                       template_sql change
  DELETE /rules/{id}                 - delete
  POST   /rules/{id}/preview-count   - runs the rule's canonical SQL
                                       and returns the row count
                                       (capped at 200) for admin UI
                                       feedback

Cross-family rule ids return 404. RuleValidationError becomes a 422
carrying the validator's bracketed tag so the admin UI can surface
stable error codes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.nudge_rules import NudgeRule
from app.schemas.nudges import (
    NudgeRuleCreate,
    NudgeRulePatch,
    NudgeRuleRead,
    PreviewCountResponse,
)
from app.services import nudges_service
from app.services.nudge_rule_validator import (
    RuleExecutionError,
    RuleValidationError,
    validate_rule_sql,
)

router = APIRouter(prefix="/api/admin/nudges", tags=["admin-nudges"])


@router.get("/rules", response_model=list[NudgeRuleRead])
def list_rules(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission("nudges.configure")
    return list(
        db.scalars(
            select(NudgeRule)
            .where(NudgeRule.family_id == actor.family_id)
            .order_by(NudgeRule.created_at.desc())
        ).all()
    )


@router.post("/rules", response_model=NudgeRuleRead)
def create_rule(
    body: NudgeRuleCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission("nudges.configure")
    try:
        validated = validate_rule_sql(body.template_sql)
    except RuleValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    rule = NudgeRule(
        family_id=actor.family_id,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        source_kind=body.source_kind,
        template_sql=body.template_sql,
        canonical_sql=validated.canonical_sql,
        template_params=body.template_params,
        trigger_kind="custom_rule",
        default_lead_time_minutes=body.default_lead_time_minutes,
        severity=body.severity,
        created_by_family_member_id=actor.member_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=NudgeRuleRead)
def patch_rule(
    rule_id: uuid.UUID,
    body: NudgeRulePatch,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission("nudges.configure")
    rule = db.get(NudgeRule, rule_id)
    if rule is None or rule.family_id != actor.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rule not found"
        )

    # Re-validate on any template_sql change. Leave canonical_sql
    # untouched on 422 so the rule stays runnable.
    if body.template_sql is not None and body.template_sql != rule.template_sql:
        try:
            validated = validate_rule_sql(body.template_sql)
        except RuleValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        rule.template_sql = body.template_sql
        rule.canonical_sql = validated.canonical_sql

    for field in (
        "name",
        "description",
        "template_params",
        "default_lead_time_minutes",
        "severity",
        "is_active",
    ):
        v = getattr(body, field)
        if v is not None:
            setattr(rule, field, v)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission("nudges.configure")
    rule = db.get(NudgeRule, rule_id)
    if rule is None or rule.family_id != actor.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rule not found"
        )
    db.delete(rule)
    db.commit()
    return None


@router.post("/rules/{rule_id}/preview-count", response_model=PreviewCountResponse)
def preview_count(
    rule_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Execute the rule's canonical SQL now and return the row count.
    Capped at 200; errors reported as PreviewCountResponse.error so the
    admin UI can render the tag without parsing HTTP status codes."""
    actor.require_permission("nudges.configure")
    rule = db.get(NudgeRule, rule_id)
    if rule is None or rule.family_id != actor.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rule not found"
        )
    if not rule.canonical_sql:
        return PreviewCountResponse(
            count=0, capped=False, error="no canonical SQL stored"
        )
    try:
        rows = nudges_service.execute_validated_rule_sql(
            db, rule.canonical_sql, rule.template_params or {}
        )
    except RuleExecutionError as e:
        return PreviewCountResponse(count=0, capped=False, error=str(e))
    # Apply family-scope filter so the preview count cannot leak
    # cross-tenant row counts. A rule authored in Family A that tries
    # to SELECT from Family B will report 0 matches here, matching what
    # scan_rule_triggers would actually dispatch.
    raw_count = len(rows)
    filtered = nudges_service.filter_rule_rows_to_family(
        db, rows, rule.family_id, rule.id, rule.name
    )
    count = len(filtered)
    return PreviewCountResponse(count=count, capped=(raw_count == 200))
