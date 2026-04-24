-- Migration 055: Phase 1 PR 1.1 - drop scout.* tables scheduled for
-- rebuild in Phase 2.
--
-- Plan: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
--       Phase 1 PR 1.1.
--
-- Five tables drop here:
--
--   1. scout.meal_transformations - per v5.1 §2 Q7, dropped entirely
--      (not rebuilt). Defined in migration 044. Its FKs into
--      public.meals stop the CASCADE-to-scout risk flagged by
--      pre-flight Part 5.8.
--
--   2. scout.task_templates - rebuilt in Phase 2 PR 2.2 with 7 new
--      native scope-contract columns (included, not_included,
--      done_means_done, supplies, photo_example_path,
--      estimated_duration_minutes, consequence_on_miss).
--
--   3. scout.task_occurrences - rebuilt in PR 2.2. FKs out to
--      task_templates and routine_templates, both of which also drop
--      in this migration.
--
--   4. scout.routine_templates - rebuilt in PR 2.2.
--
--   5. scout.routine_steps - added to the drop set during PR 1.1
--      execution. Its FK to scout.routine_templates (ON DELETE
--      CASCADE) blocks DROP TABLE scout.routine_templates without
--      CASCADE, which the plan forbids. Phase 2 PR 2.2 is "additive
--      DDL only" (CREATE TABLE IF NOT EXISTS is a no-op against an
--      existing table), so if routine_steps stayed, its FK would
--      never come back. Dropping it here makes PR 2.2's fresh
--      CREATE TABLE statement re-establish both FKs
--      (routine_template_id + standard_of_done_id) cleanly. See PR
--      1.1 handoff "Ambiguity 2".
--
-- Order matters for clean drops without CASCADE. Migration 054
-- already dropped every FK on retained scout.* tables that pointed
-- into this set. The remaining FKs live on tables being dropped here
-- and are released naturally as each table drops.
--
-- Order of DROPs below:
--   - routine_steps first (releases routine_steps.routine_template_id
--     FK that would otherwise block routine_templates).
--   - task_occurrences second (releases its own task_template_id and
--     routine_template_id FKs).
--   - task_templates third (nothing references it now).
--   - routine_templates fourth (nothing references it now).
--   - meal_transformations last (independent; could run anywhere).
--
-- Not dropped here, though also listed under v5.1 §Phase 2 PR 2.2
-- "Build": scout.standards_of_done, scout.daily_win_results. Both
-- exist today and their current schemas are compatible with PR 2.2's
-- CREATE TABLE IF NOT EXISTS (no-op). scout.task_occurrence_step_completions
-- and scout.personal_tasks do not exist today; PR 2.2 creates them
-- fresh.

BEGIN;

DROP TABLE IF EXISTS scout.routine_steps;
DROP TABLE IF EXISTS scout.task_occurrences;
DROP TABLE IF EXISTS scout.task_templates;
DROP TABLE IF EXISTS scout.routine_templates;
DROP TABLE IF EXISTS scout.meal_transformations;

COMMIT;
