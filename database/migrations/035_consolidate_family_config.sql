-- Migration 035: Consolidate public.family_config into scout.household_rules
--
-- public.family_config (created by migration 024) is superseded by
-- scout.household_rules (created by migration 022), which is the canonical
-- home for all family-level key/value configuration.
--
-- Step 1: Copy all public.family_config rows into scout.household_rules.
-- Step 2: Drop public.family_config.
--
-- No view refresh required — scout.household_rules is a native table in the
-- scout schema, not an alias of a public table, so there is no view to
-- recreate.

-- Step 1: Copy rows (upsert — handles any pre-existing household_rules rows
-- that share the same (family_id, rule_key) pair, e.g. the seed rows written
-- by migration 023 for the Roberts household).
INSERT INTO scout.household_rules (family_id, rule_key, rule_value, description, created_at, updated_at)
SELECT fc.family_id, fc.key, fc.value, NULL, fc.created_at, fc.updated_at
FROM family_config fc
ON CONFLICT (family_id, rule_key) DO UPDATE
    SET rule_value = EXCLUDED.rule_value,
        updated_at = EXCLUDED.updated_at;

-- Step 2: Drop the now-redundant table.
DROP TABLE IF EXISTS family_config;
