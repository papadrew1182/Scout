"""Sprint 2 Backlog #4 — the weekly meal plan generator must surface
each family member's dietary preferences into the prompt it sends to
Anthropic, and the system prompt must carry explicit constraint-handling
rules so the model can't silently ignore them.

These tests assert the contract at the *prompt* layer (what we send to
Anthropic), not the *output* layer (what Anthropic returns). We cannot
assert "the AI avoided nut-based staples" without burning real tokens,
but we can guarantee the allergy data reached the request body.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.meals import DietaryPreference
from app.services import weekly_meal_plan_service


def _next_monday() -> date:
    """Strictly-future Monday. ``weekday()`` returns Mon=0..Sun=6."""
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7
    return today + timedelta(days=days_ahead or 7)


def _fake_plan_payload() -> dict:
    """Minimal ready-plan JSON the generator's validator will accept."""
    return {
        "status": "ready",
        "week_plan": {
            "dinners": {
                day: {"title": f"{day} meal", "description": "nut-free"}
                for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
            },
            "breakfast": {"plan": "oats + fruit"},
            "lunch": {"plan": "sandwiches"},
            "snacks": ["apple", "carrots"],
        },
        "prep_plan": {
            "tasks": [
                {"title": "Chop veg", "supports": ["monday"], "duration_min": 20},
            ],
            "timeline": [{"block": "0:00-0:30", "items": ["chop"]}],
        },
        "grocery_plan": {
            "stores": [
                {
                    "name": "Costco",
                    "items": [{"title": "Chicken", "quantity": 2, "unit": "lb"}],
                }
            ]
        },
        "plan_summary": "nut-free test plan",
    }


def _fake_provider(payload: dict) -> MagicMock:
    """Return a MagicMock provider whose chat() yields `payload` as JSON."""
    provider = MagicMock()
    provider.chat.return_value = SimpleNamespace(
        content=json.dumps(payload),
        model="claude-opus-4-6",
        input_tokens=100,
        output_tokens=200,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        stop_reason="end_turn",
        tool_calls=[],
    )
    return provider


class TestDietaryPrefsInGeneratorPrompt:
    def test_nut_allergy_pref_appears_in_user_prompt(
        self, db: Session, family, adults, children, monkeypatch
    ):
        """A child's nut allergy must be in the constraints block of the
        user prompt sent to Anthropic, under the exact kind+label we
        stored. This is the regression trap for Sprint 2 #4."""
        monkeypatch.setenv("SCOUT_ENABLE_MEAL_GENERATION", "true")
        # Live pydantic settings is module-level; monkeypatch the attr too.
        from app.config import settings
        monkeypatch.setattr(settings, "enable_meal_generation", True)

        sadie = children["sadie"]
        db.add(
            DietaryPreference(
                family_member_id=sadie.id,
                label="peanut_allergy",
                kind="allergy",
                notes="epipen required",
            )
        )
        db.commit()

        provider = _fake_provider(_fake_plan_payload())
        andrew = adults["robert"]

        weekly_meal_plan_service.generate_weekly_meal_plan(
            db,
            family.id,
            andrew.id,
            week_start_date=_next_monday(),
            provider=provider,
        )

        provider.chat.assert_called_once()
        call_kwargs = provider.chat.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert isinstance(user_msg, str)
        user_payload = json.loads(user_msg)
        dietary_entries = user_payload.get("constraints", {}).get("dietary", [])
        assert dietary_entries, "constraints.dietary must be present even if empty-ish"
        allergy_row = next(
            (d for d in dietary_entries if d["label"] == "peanut_allergy"), None
        )
        assert allergy_row is not None, "peanut_allergy row missing from constraints"
        assert allergy_row["kind"] == "allergy"
        assert allergy_row["member_id"] == str(sadie.id)

    def test_system_prompt_has_dietary_constraint_rules(self):
        """The system prompt must explicitly mention how to handle nut
        allergies (and other common restrictions) so the model can't
        silently skip them. This locks the contract — if someone
        unwittingly weakens SYSTEM_PROMPT, the test fires."""
        prompt = weekly_meal_plan_service.SYSTEM_PROMPT
        # Nut allergy is the canonical example in the plan.
        assert "nut allergy" in prompt.lower()
        assert "peanut" in prompt.lower() or "nut" in prompt.lower()
        # We also want explicit direction that the "just skip the meat"
        # dodge isn't acceptable for vegetarians.
        assert "vegetarian" in prompt.lower()

    def test_family_with_no_prefs_still_includes_dietary_key(
        self, db: Session, family, adults, monkeypatch
    ):
        """Empty `dietary` is still sent so the model can't confuse
        'no preferences set' with 'the field is missing from the
        schema'. Prevents a regression where the JSON key silently
        disappears when the family has no prefs."""
        from app.config import settings
        monkeypatch.setattr(settings, "enable_meal_generation", True)

        provider = _fake_provider(_fake_plan_payload())
        andrew = adults["robert"]

        weekly_meal_plan_service.generate_weekly_meal_plan(
            db,
            family.id,
            andrew.id,
            week_start_date=_next_monday(),
            provider=provider,
        )

        payload = json.loads(provider.chat.call_args.kwargs["messages"][0]["content"])
        assert "dietary" in payload.get("constraints", {})
        assert isinstance(payload["constraints"]["dietary"], list)
