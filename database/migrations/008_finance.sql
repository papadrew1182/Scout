-- Migration 008: Finance
-- Source of truth: BACKEND_ROADMAP.md + Scout conventions
-- Generated: 2026-04-09
--
-- 1 table: bills
--
-- Intentionally minimal. No budget engine, no accounts, no reconciliation,
-- no recurring-bill expansion. A recurring monthly bill is multiple rows.
-- External IDs (e.g., YNAB transaction ids) live in connector_mappings.
--
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- bills
-- ============================================================================
-- One row per household bill / obligation. Family-scoped via denormalized
-- family_id; write-path must validate family_id matches the creator's family.
--
-- amount_cents is a signed integer for safety, but in practice all bills
-- are positive obligations. Negative amounts are not currently supported by
-- the service layer.

CREATE TABLE IF NOT EXISTS bills (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    created_by   uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    title        text        NOT NULL,
    description  text,
    notes        text,
    amount_cents integer     NOT NULL,
    due_date     date        NOT NULL,
    status       text        NOT NULL DEFAULT 'upcoming',
    paid_at      timestamptz,
    source       text        NOT NULL DEFAULT 'scout',
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_bills_status
        CHECK (status IN ('upcoming', 'paid', 'overdue', 'cancelled')),

    CONSTRAINT chk_bills_source
        CHECK (source IN ('scout', 'ynab')),

    -- title cannot be empty/whitespace-only
    CONSTRAINT chk_bills_title_not_blank
        CHECK (length(btrim(title)) > 0),

    -- bills must have a non-negative amount
    CONSTRAINT chk_bills_amount_nonneg
        CHECK (amount_cents >= 0),

    -- paid_at is set iff status is paid
    CONSTRAINT chk_bills_paid_consistency
        CHECK (
            (status = 'paid' AND paid_at IS NOT NULL)
            OR (status != 'paid' AND paid_at IS NULL)
        )
);

-- Primary read paths
CREATE INDEX idx_bills_family_due_date
    ON bills (family_id, due_date);

CREATE INDEX idx_bills_family_status
    ON bills (family_id, status);

-- FK index
CREATE INDEX idx_bills_created_by ON bills (created_by);

CREATE TRIGGER trg_bills_updated_at
    BEFORE UPDATE ON bills
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
