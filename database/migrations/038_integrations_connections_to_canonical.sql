-- Migration 038: Migrate integrations.connections from scout.household_rules
--                into scout.connector_accounts (normalized rows).
--
-- The household_rules row with rule_key = 'integrations.connections' holds
-- a JSONB value like:
--   { "connections": [
--       { "id": "google_calendar", "name": "Google Calendar",
--         "status": "connected", "category": "calendar" }, ...
--   ] }
--
-- scout.connectors is already seeded (migration 022) with the canonical
-- connector registry. This migration creates per-family connector_accounts
-- rows by matching connection.id to scout.connectors.connector_key.
--
-- Status mapping:
--   "connected"      → 'connected'
--   "needs_reauth"   → 'error'
--   "not_connected"  → 'disconnected'
--   (anything else)  → 'disconnected'
--
-- Idempotent: ON CONFLICT DO NOTHING on the implicit PK / existing unique
-- path (there is no unique constraint on (connector_id, family_id) in the
-- 022 schema, so we use a sub-select guard to avoid duplicate inserts on
-- re-run).
--
-- After migration the source row is deleted from scout.household_rules.

DO $$
DECLARE
    hr           RECORD;
    conn         RECORD;
    v_connector_id UUID;
    v_status       TEXT;
BEGIN
    FOR hr IN
        SELECT rule.family_id, rule.rule_value
        FROM   scout.household_rules rule
        WHERE  rule.rule_key = 'integrations.connections'
    LOOP
        FOR conn IN
            SELECT c.value AS v
            FROM   jsonb_array_elements(hr.rule_value -> 'connections') AS c
        LOOP
            -- Resolve the matching scout.connectors row by connector_key
            SELECT id INTO v_connector_id
            FROM   scout.connectors
            WHERE  connector_key = conn.v ->> 'id';

            -- Skip entries whose id does not match any seeded connector
            IF v_connector_id IS NULL THEN
                CONTINUE;
            END IF;

            -- Map the legacy status string to the canonical vocabulary
            v_status := CASE conn.v ->> 'status'
                WHEN 'connected'    THEN 'connected'
                WHEN 'needs_reauth' THEN 'error'
                WHEN 'not_connected' THEN 'disconnected'
                ELSE                     'disconnected'
            END;

            -- Guard against duplicate rows on idempotent re-run
            IF NOT EXISTS (
                SELECT 1
                FROM   scout.connector_accounts ca
                WHERE  ca.connector_id = v_connector_id
                  AND  ca.family_id    = hr.family_id
            ) THEN
                INSERT INTO scout.connector_accounts (
                    connector_id,
                    family_id,
                    status,
                    account_label
                ) VALUES (
                    v_connector_id,
                    hr.family_id,
                    v_status,
                    conn.v ->> 'name'
                );
            END IF;
        END LOOP;
    END LOOP;
END $$;

-- Clean up source row once migrated.
DELETE FROM scout.household_rules WHERE rule_key = 'integrations.connections';
