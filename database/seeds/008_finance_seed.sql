-- Seed 008: Finance
-- Realistic household bills for the Whitfield family.
-- Requires: 008_finance.sql migration applied first.
--
-- UUID reference (from foundation seed):
-- family:  a1b2c3d4-0000-4000-8000-000000000001
-- Andrew:  b1000000-0000-4000-8000-000000000001
-- Sally:   b1000000-0000-4000-8000-000000000002

BEGIN;

-- ============================================================================
-- bills (one month of household obligations)
-- ============================================================================

-- Upcoming bills
INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, source)
VALUES
    ('c0000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Mortgage',
     'First-of-month payment to First National',
     245000, '2026-05-01', 'upcoming', 'scout');

INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, source)
VALUES
    ('c0000000-0001-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Electric',
     'City Power & Light — April usage',
     14523, '2026-04-22', 'upcoming', 'scout');

INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, source)
VALUES
    ('c0000000-0001-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Internet',
     'Fiber 1Gig — monthly',
     8999, '2026-04-18', 'upcoming', 'scout');

INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, source)
VALUES
    ('c0000000-0001-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Car insurance',
     'Six-month renewal',
     67800, '2026-04-25', 'upcoming', 'scout');

-- Overdue bill (past due date, still upcoming status — service will surface as overdue)
INSERT INTO bills (id, family_id, created_by, title, description, notes,
                    amount_cents, due_date, status, source)
VALUES
    ('c0000000-0001-4000-8000-000000000005',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Garbage service',
     'Quarterly waste pickup',
     'Andrew forgot to schedule autopay',
     7500, '2026-04-05', 'overdue', 'scout');

-- Paid bills (history)
INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, paid_at, source)
VALUES
    ('c0000000-0001-4000-8000-000000000006',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Water',
     'City water — March usage',
     6234, '2026-04-03', 'paid', '2026-04-02 09:15:00-05', 'scout');

INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, paid_at, source)
VALUES
    ('c0000000-0001-4000-8000-000000000007',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Streaming bundle',
     'Disney+ / Hulu / ESPN+',
     1899, '2026-04-07', 'paid', '2026-04-07 08:00:00-05', 'ynab');

-- A YNAB-sourced upcoming bill
INSERT INTO bills (id, family_id, created_by, title, description,
                    amount_cents, due_date, status, source)
VALUES
    ('c0000000-0001-4000-8000-000000000008',
     'a1b2c3d4-0000-4000-8000-000000000001',
     NULL,
     'Cell phone (family plan)',
     'Synced from YNAB scheduled transaction',
     18450, '2026-04-20', 'upcoming', 'ynab');

-- ============================================================================
-- connector_mappings — link the YNAB bills to their YNAB scheduled txn ids
-- ============================================================================

INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id,
                                 external_id, metadata)
VALUES
    ('aa000000-0008-4000-8000-000000000001',
     'ynab', 'bills',
     'c0000000-0001-4000-8000-000000000007',
     'ynab_txn_streaming_2026_04',
     '{"resource_type": "scheduled_transaction"}');

INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id,
                                 external_id, metadata)
VALUES
    ('aa000000-0008-4000-8000-000000000002',
     'ynab', 'bills',
     'c0000000-0001-4000-8000-000000000008',
     'ynab_txn_cell_phone_2026_04',
     '{"resource_type": "scheduled_transaction"}');

COMMIT;
