# Phase 5 Handoff - Meal Base-Cook Model

**Branch:** `sprint/operability-phase-5-meal-base-cooks`
**Date:** 2026-04-19

---

## Migrations added

- `044_meal_base_cooks.sql` - base-cook columns on meals, meal_transformations table

## Tables / columns added

| Table | Columns |
|-------|---------|
| `meals` | is_base_cook, base_cook_yield_servings, base_cook_keeps_days, storage_notes |
| `scout.meal_transformations` | New table: base-to-transformed meal mapping |
| `weekly_meal_plan_entries` | is_base_cook_execution, base_cook_source_entry_id (if table exists) |

## Endpoints added

| Endpoint | Description |
|----------|-------------|
| `GET /meals/base-cooks/{staple_id}/transformations` | List transformation options for a base-cook staple |

## Known follow-ups

- Generator prompt upgrade for use_base_cook_planning family_config flag
- Frontend base-cook marker rendering on planner view
- "Double it" action on base-cook nights
- Seed 6-10 base-cook staples from project file

## Narrative summary

Phase 5 extended the meal model with base-cook support. Four columns
were added to the meals table for base-cook metadata. A new
meal_transformations table enables mapping base cooks to their
transformed meal outputs. The transformations endpoint supports
planner autocomplete.
