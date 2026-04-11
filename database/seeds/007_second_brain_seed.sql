-- Seed 007: Second Brain
-- Realistic notes for Andrew and Sally.
-- Requires: 007_second_brain.sql migration applied first.
--
-- UUID reference (from foundation seed):
-- family:  a1b2c3d4-0000-4000-8000-000000000001
-- Andrew:  b1000000-0000-4000-8000-000000000001
-- Sally:   b1000000-0000-4000-8000-000000000002

BEGIN;

-- ============================================================================
-- Andrew's notes
-- ============================================================================

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Q2 Strategic Priorities',
     E'Top three priorities for Q2:\n1. Ship the new onboarding flow\n2. Hire two senior engineers\n3. Reduce infra costs by 15%',
     'work');

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Garden plan',
     E'Spring planting:\n- Tomatoes (heirloom)\n- Basil\n- Bell peppers\n- Zucchini\nCheck soil pH before planting.',
     'home');

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Books to read',
     E'- The Making of a Manager — Julie Zhuo\n- Working Backwards — Colin Bryar\n- Shape Up — Ryan Singer (re-read)',
     'reading');

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Sadie college fund — research',
     E'529 vs UTMA notes:\n- 529 grows tax-free for qualified education\n- UTMA has more flexibility but counts against financial aid\n- Need to talk with financial advisor in May',
     'finance');

-- An archived note
INSERT INTO notes (id, family_id, family_member_id, title, body, category, is_archived)
VALUES
    ('b0000000-0001-4000-8000-000000000005',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Old project notes — Q4 2025',
     E'Closed out — moved to archive after the Dec retrospective.',
     'work',
     true);

-- ============================================================================
-- Sally's notes
-- ============================================================================

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000006',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Sadie''s 14th birthday ideas',
     E'- Sleepover with 4 friends\n- Pottery painting party\n- Concert tickets (need to ask Andrew about budget)\nNeed to decide by end of April.',
     'family');

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000007',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'River allergy notes',
     E'Tree nut allergy — strict avoidance.\n- EpiPen at school nurse + backup at home\n- Read every label\n- Dr. Martinez follow-up next month',
     'health');

INSERT INTO notes (id, family_id, family_member_id, title, body, category)
VALUES
    ('b0000000-0001-4000-8000-000000000008',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Recipe ideas — quick weeknight',
     E'- Sheet pan salmon + asparagus (20 min)\n- Chicken stir fry over rice\n- Black bean tacos\n- Pesto pasta with peas\nKids will eat all of these.',
     'meals');

COMMIT;
