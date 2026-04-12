-- Migration 011: Grocery Items + Purchase Requests
-- Universal acquisition flow for household needs.
-- Depends on: 001_foundation_connectors.sql, 005_meals.sql

BEGIN;

-- ============================================================================
-- grocery_items
-- ============================================================================
-- Canonical grocery list. All sources converge here:
-- meal_ai, manual additions, approved purchase requests.

CREATE TABLE IF NOT EXISTS grocery_items (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id            uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    added_by_member_id   uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    title                text        NOT NULL,
    quantity             numeric,
    unit                 text,
    category             text,
    preferred_store      text,
    notes                text,
    source               text        NOT NULL DEFAULT 'manual',
    approval_status      text        NOT NULL DEFAULT 'active',
    purchase_request_id  uuid,
    is_purchased         boolean     NOT NULL DEFAULT false,
    purchased_at         timestamptz,
    purchased_by         uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_grocery_items_source
        CHECK (source IN ('meal_ai', 'manual', 'purchase_request')),
    CONSTRAINT chk_grocery_items_approval_status
        CHECK (approval_status IN ('active', 'pending_review', 'approved', 'rejected')),
    CONSTRAINT chk_grocery_items_title_not_blank
        CHECK (length(btrim(title)) > 0)
);

CREATE INDEX idx_grocery_items_family_status
    ON grocery_items (family_id, approval_status);
CREATE INDEX idx_grocery_items_family_purchased
    ON grocery_items (family_id, is_purchased);
CREATE INDEX idx_grocery_items_added_by
    ON grocery_items (added_by_member_id);

CREATE TRIGGER trg_grocery_items_updated_at
    BEFORE UPDATE ON grocery_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- purchase_requests
-- ============================================================================

CREATE TABLE IF NOT EXISTS purchase_requests (
    id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id              uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    requested_by_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    type                   text        NOT NULL DEFAULT 'grocery',
    title                  text        NOT NULL,
    details                text,
    quantity               numeric,
    unit                   text,
    preferred_brand        text,
    preferred_store        text,
    urgency                text,
    status                 text        NOT NULL DEFAULT 'pending',
    linked_grocery_item_id uuid        REFERENCES grocery_items (id) ON DELETE SET NULL,
    reviewed_by_member_id  uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    reviewed_at            timestamptz,
    review_note            text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_purchase_requests_type
        CHECK (type IN ('grocery', 'household', 'personal', 'other')),
    CONSTRAINT chk_purchase_requests_status
        CHECK (status IN ('pending', 'approved', 'rejected', 'converted', 'fulfilled')),
    CONSTRAINT chk_purchase_requests_urgency
        CHECK (urgency IS NULL OR urgency IN ('low', 'normal', 'high', 'urgent')),
    CONSTRAINT chk_purchase_requests_title_not_blank
        CHECK (length(btrim(title)) > 0)
);

CREATE INDEX idx_purchase_requests_family_status
    ON purchase_requests (family_id, status);
CREATE INDEX idx_purchase_requests_requested_by
    ON purchase_requests (requested_by_member_id);
CREATE INDEX idx_purchase_requests_reviewed_by
    ON purchase_requests (reviewed_by_member_id)
    WHERE reviewed_by_member_id IS NOT NULL;

CREATE TRIGGER trg_purchase_requests_updated_at
    BEFORE UPDATE ON purchase_requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Add FK from grocery_items to purchase_requests now that both tables exist
ALTER TABLE grocery_items
    ADD CONSTRAINT fk_grocery_items_purchase_request
    FOREIGN KEY (purchase_request_id) REFERENCES purchase_requests (id) ON DELETE SET NULL;

CREATE INDEX idx_grocery_items_purchase_request
    ON grocery_items (purchase_request_id)
    WHERE purchase_request_id IS NOT NULL;

COMMIT;
