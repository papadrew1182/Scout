-- Migration 004: Add 'ical' to connector_configs and connector_mappings
-- Source of truth: BACKEND_ROADMAP.md follow-up to Calendar package
-- Generated: 2026-04-09
--
-- The Calendar package introduced events.source = 'ical', but the existing
-- connector layer CHECK constraints do not allow 'ical' as a connector_name.
-- This migration extends both CHECK constraints to include 'ical'.
--
-- No data is altered. Existing rows remain valid under the new (broader) check.
--
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- connector_configs: extend allowed connector_name values
-- ============================================================================

ALTER TABLE connector_configs
    DROP CONSTRAINT chk_connector_configs_connector_name;

ALTER TABLE connector_configs
    ADD CONSTRAINT chk_connector_configs_connector_name
    CHECK (connector_name IN (
        'google_calendar', 'hearth', 'ynab', 'apple_health', 'rex', 'ical'
    ));

-- ============================================================================
-- connector_mappings: extend allowed connector_name values
-- ============================================================================

ALTER TABLE connector_mappings
    DROP CONSTRAINT chk_connector_mappings_connector_name;

ALTER TABLE connector_mappings
    ADD CONSTRAINT chk_connector_mappings_connector_name
    CHECK (connector_name IN (
        'google_calendar', 'hearth', 'ynab', 'apple_health', 'rex', 'ical'
    ));

COMMIT;
